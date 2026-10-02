"""
Event-Driven Stream Worker for Agri Telemetry & Forecasting Platform.
Consumes telemetry events, executes validation, state construction, forecasting, risk evaluation, and emits downstream events.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Dict, List, Optional, Any

from agri_telemetry.contracts.telemetry_event import TelemetryEvent
from agri_telemetry.contracts.forecast_event import ForecastEvent
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.contracts.validator import validate_telemetry_event
from agri_telemetry.domain.enums import TargetVariable, AlertCategory
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.qc.engine import Tier1QCEngine
from agri_telemetry.state.state_builder import StateBuilder, SoilProfileConfig
from agri_telemetry.decision.advisory_engine import OperationalAdvisoryEngine
from agri_telemetry.forecasting.persistence import PersistenceModel
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator
from agri_telemetry.forecasting.engine import ForecastingEngine

from agri_telemetry.streaming.broker import EventStreamBroker, InMemoryStreamBroker, StreamMessage
from agri_telemetry.storage.sqlite_store import SQLiteStore
from agri_telemetry.observability.logging import setup_logger, trace_stage, set_correlation_id
from agri_telemetry.observability.metrics import MetricsCollector, platform_metrics


@dataclass
class WorkerBatchResult:
    """Summary of a worker batch processing cycle."""
    processed_count: int = 0
    valid_count: int = 0
    quarantined_count: int = 0
    forecasts_emitted: int = 0
    alerts_emitted: int = 0
    errors_count: int = 0
    elapsed_ms: float = 0.0


class TelemetryStreamWorker:
    """
    Asynchronous event-stream processor that executes the complete operational pipeline.
    """

    def __init__(
        self,
        broker: Optional[EventStreamBroker] = None,
        store: Optional[SQLiteStore] = None,
        telemetry_stream: str = "stream:telemetry",
        forecast_stream: str = "stream:forecasts",
        alert_stream: str = "stream:alerts",
        consumer_group: str = "agri_workers",
        soil_config: Optional[SoilProfileConfig] = None,
        metrics: Optional[MetricsCollector] = None,
    ):
        self.broker = broker or InMemoryStreamBroker()
        self.store = store or SQLiteStore()
        self.telemetry_stream = telemetry_stream
        self.forecast_stream = forecast_stream
        self.alert_stream = alert_stream
        self.consumer_group = consumer_group
        self.metrics = metrics or platform_metrics
        self.logger = setup_logger("agri_telemetry.worker")

        # Core pipeline components
        self.state_builder = StateBuilder(soil_config=soil_config or SoilProfileConfig())
        self.advisory_engine = OperationalAdvisoryEngine()
        self.persistence_forecaster = PersistenceModel(horizons=[1, 6, 12, 24, 48, 72, 168])
        self.calibrator = EmpiricalUncertaintyCalibrator(horizons=[1, 6, 12, 24, 48, 72, 168])
        self.forecasting_engine = ForecastingEngine(calibrator=self.calibrator, horizons=[1, 6, 12, 24, 48, 72, 168])

    def process_next_batch(self, batch_size: int = 10) -> WorkerBatchResult:
        """Consumes and processes a batch of telemetry stream messages."""
        start_time = time.perf_counter()
        result = WorkerBatchResult()

        messages: List[StreamMessage] = self.broker.consume(
            stream_name=self.telemetry_stream,
            consumer_group=self.consumer_group,
            batch_size=batch_size,
        )

        for msg in messages:
            set_correlation_id(msg.correlation_id)
            result.processed_count += 1
            self.metrics.record_ingested_event(valid=True)

            try:
                # 1. Parse and validate TelemetryEvent contract
                with trace_stage("contract_validation", self.logger):
                    if isinstance(msg.payload, dict):
                        # Validate schema
                        is_valid_schema, schema_err = validate_telemetry_event(msg.payload)
                        if not is_valid_schema:
                            self.logger.warning(f"Schema validation failed: {schema_err}")
                            self.metrics.record_error()
                            result.errors_count += 1
                            continue
                        event = TelemetryEvent.model_validate(msg.payload)
                    elif isinstance(msg.payload, TelemetryEvent):
                        event = msg.payload
                    else:
                        raise ValueError(f"Unsupported payload type: {type(msg.payload)}")

                # 2. State Construction
                state: Optional[SoilWaterState] = None
                with trace_stage("state_construction", self.logger):
                    state = self.state_builder.build_state(event)
                    if state and state.is_valid:
                        result.valid_count += 1
                        self.metrics.record_scientific_metrics(latest_depletion=state.depletion_fraction)

                # 3. Decision Cycle (QC, Physical Deviation, Water Risk, Persistence)
                with trace_stage("advisory_evaluation", self.logger):
                    forecast_dict: Optional[Dict[int, Dict[str, Any]]] = None
                    if state and state.is_valid:
                        # Generate baseline forecast for risk evaluation
                        pt_forecasts = self.persistence_forecaster.predict(state.theta_rz)
                        forecast_dict = {}
                        for h in [1, 6, 12, 24, 48, 72, 168]:
                            pt = pt_forecasts.get(h, state.theta_rz) if isinstance(pt_forecasts, dict) else state.theta_rz
                            if self.calibrator.is_calibrated:
                                quantiles = self.calibrator.calculate_quantiles(pt, horizon_hours=h)
                                q10, q50, q90 = quantiles["q10"], quantiles["q50"], quantiles["q90"]
                            else:
                                q10, q50, q90 = pt, pt, pt
                            forecast_dict[h] = {
                                "point_forecast": pt,
                                "q10": q10,
                                "q50": q50,
                                "q90": q90,
                                "width": max(0.0, q90 - q10),
                            }

                    cycle_res = self.advisory_engine.process_cycle(
                        event=event,
                        state=state,
                        forecast_predictions=forecast_dict,
                    )

                # 4. Handle Quarantine or Outflow
                if cycle_res.is_quarantined:
                    result.quarantined_count += 1
                    self.metrics.record_quarantine()
                else:
                    # Publish ForecastEvent if state was valid
                    if state and state.is_valid:
                        fc_event = self.forecasting_engine.generate_forecast(state=state)
                        self.broker.publish(
                            stream_name=self.forecast_stream,
                            payload=fc_event.to_dict(),
                            event_time=fc_event.forecast_origin_time,
                            correlation_id=msg.correlation_id,
                        )
                        self.store.store_forecast_event(fc_event)
                        result.forecasts_emitted += 1
                        self.metrics.record_forecast_emitted()

                # 5. Publish Confirmed Advisories to Alert Stream
                for adv in cycle_res.confirmed_advisories:
                    self.broker.publish(
                        stream_name=self.alert_stream,
                        payload=adv.to_dict(),
                        event_time=adv.trigger_time,
                        correlation_id=msg.correlation_id,
                    )
                    self.store.store_alert_event(adv)
                    result.alerts_emitted += 1
                    self.metrics.record_advisory_emitted(category=adv.category.value, severity=adv.severity.value)

                # 6. Acknowledge message
                self.broker.acknowledge(
                    stream_name=self.telemetry_stream,
                    consumer_group=self.consumer_group,
                    message_id=msg.message_id,
                )

            except Exception as ex:
                self.logger.exception(f"Error processing stream message {msg.message_id}: {ex}")
                self.metrics.record_error()
                result.errors_count += 1

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        result.elapsed_ms = elapsed_ms
        self.metrics.record_pipeline_latency(elapsed_ms)
        return result

    def close(self) -> None:
        """Closes internal store connection."""
        self.store.close()

