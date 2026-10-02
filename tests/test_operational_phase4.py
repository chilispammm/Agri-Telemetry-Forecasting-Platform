"""
Authoritative Test Suite for Phase 4: Operationalisation & MLOps Engineering.
Validates:
1. Configuration Management (Separation of scientific, operational, and secrets)
2. Observability & Structured JSON Logging (Trace stages, correlation IDs)
3. Operational vs Scientific Metrics Collection
4. MLOps Experiment Tracking & Model Lineage
5. In-Memory Event Streaming Broker & Worker Pipeline
6. Reliability, Fault Tolerance & Recovery (DLQ, Deduplication, Sequencer, Fallback Router)
7. End-to-End Operational Pipeline
"""

import json
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from agri_telemetry.config.settings import (
    AppConfig, SoilConfig, RiskConfig, ForecastingConfig,
    StreamingConfig, ObservabilityConfig, StorageConfig, MLOpsConfig, ReliabilityConfig
)
from agri_telemetry.observability.logging import (
    setup_logger, trace_stage, set_correlation_id, set_run_id, JSONFormatter
)
from agri_telemetry.observability.metrics import MetricsCollector, LatencyTracker
from agri_telemetry.mlops.experiment_tracker import (
    ExperimentTracker, ExperimentRunContext, ExperimentRunManifest, get_git_commit_sha
)
from agri_telemetry.streaming.broker import (
    InMemoryStreamBroker, StreamMessage, RedisStreamBroker
)
from agri_telemetry.streaming.worker import TelemetryStreamWorker, WorkerBatchResult
from agri_telemetry.reliability.recovery import (
    DeadLetterQueue, DeadLetterItem, EventDeduplicator, OutOfOrderSequencer, ResilientForecastRouter
)
from agri_telemetry.pipeline import OperationalPipeline
from agri_telemetry.contracts.telemetry_event import (
    TelemetryEvent, TelemetryMeasurement
)
from agri_telemetry.contracts.forecast_event import ForecastEvent
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.domain.enums import TargetVariable, AlertCategory, AlertSeverity, DataClass, VariableName, Unit, QCFlag
from agri_telemetry.forecasting.persistence import PersistenceModel



# ============================================================================
# 1. Configuration Management Tests
# ============================================================================

def test_app_config_defaults_and_yaml_io():
    """Verify default configuration hierarchy and YAML round-trip serialization."""
    config = AppConfig()
    assert config.station_id == "USCRN_NE_Lincoln_11_SW"
    assert config.soil.theta_fc == 0.33
    assert config.risk.d_mad == 0.50
    assert config.forecasting.model_strategy == "HORIZON_PARTITIONED"
    assert config.streaming.broker_type == "IN_MEMORY"
    assert config.reliability.fallback_to_persistence is True

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.yaml"
        config.save_yaml(config_path)
        assert config_path.exists()

        loaded = AppConfig.from_yaml(config_path)
        assert loaded.station_id == config.station_id
        assert loaded.soil.theta_fc == config.soil.theta_fc
        assert loaded.risk.action_horizon_hours == 24


def test_app_config_env_overrides(monkeypatch):
    """Verify operational environment variable overrides."""
    monkeypatch.setenv("AGRI_STATION_ID", "CUSTOM_STATION_99")
    monkeypatch.setenv("AGRI_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("AGRI_STREAM_BROKER", "REDIS")
    monkeypatch.setenv("AGRI_REDIS_PORT", "6380")
    monkeypatch.setenv("AGRI_MLOPS_BACKEND", "MLFLOW")

    config = AppConfig.from_env()
    assert config.station_id == "CUSTOM_STATION_99"
    assert config.observability.log_level == "DEBUG"
    assert config.streaming.broker_type == "REDIS"
    assert config.streaming.redis_port == 6380
    assert config.mlops.tracking_backend == "MLFLOW"


# ============================================================================
# 2. Observability & Structured Logging Tests
# ============================================================================

def test_structured_json_logging_and_tracing(capsys):
    """Verify structured JSON logging and trace_stage context manager."""
    logger = setup_logger(
        name="test_logger",
        level="DEBUG",
        log_format="json",
        service_name="test-service",
        environment="test",
    )
    set_correlation_id("corr-12345")
    set_run_id("run-67890")

    with trace_stage("unit_test_stage", logger=logger, extra={"test_key": "test_val"}):
        pass

    captured = capsys.readouterr()
    lines = [l for l in captured.out.strip().split("\n") if l.strip()]
    assert len(lines) >= 1

    last_entry = json.loads(lines[-1])
    assert last_entry["service"] == "test-service"
    assert last_entry["environment"] == "test"
    assert last_entry["correlation_id"] == "corr-12345"
    assert last_entry["run_id"] == "run-67890"


# ============================================================================
# 3. Operational vs Scientific Metrics Collection Tests
# ============================================================================

def test_metrics_collector_operational_vs_scientific():
    """Verify strict separation and calculation of operational vs scientific metrics."""
    metrics = MetricsCollector()
    
    # Operational metrics
    metrics.record_ingested_event(valid=True)
    metrics.record_ingested_event(valid=True)
    metrics.record_quarantine(count=1)
    metrics.record_forecast_emitted(count=2)
    metrics.record_advisory_emitted(category="AGRONOMIC_RISK", severity="WARNING")
    metrics.record_error(count=1)
    metrics.record_pipeline_latency(15.5)
    metrics.record_pipeline_latency(24.5)
    metrics.record_stage_latency("state_construction", 4.2)

    # Scientific metrics
    metrics.record_scientific_metrics(
        mae={1: 0.005, 24: 0.012},
        rmse={1: 0.007, 24: 0.015},
        coverage={1: 0.96, 24: 0.88},
        skill={1: 0.75, 24: 0.12},
        latest_depletion=0.45,
    )

    summary = metrics.to_dict()

    # Verify operational section
    op = summary["operational_metrics"]
    assert op["events_ingested_total"] == 2
    assert op["events_valid_total"] == 2
    assert op["events_quarantined_total"] == 1
    assert op["forecasts_generated_total"] == 2
    assert op["advisories_emitted_total"] == 1
    assert op["errors_total"] == 1
    assert op["pipeline_latency_ms"]["count"] == 2
    assert op["pipeline_latency_ms"]["mean"] == pytest.approx(20.0, rel=1e-2)
    assert "state_construction" in op["stage_latencies_ms"]

    # Verify scientific section
    sci = summary["scientific_metrics"]
    assert sci["forecast_mae"][1] == 0.005
    assert sci["forecast_mae"][24] == 0.012
    assert sci["interval_80_coverage"][1] == 0.96
    assert sci["skill_vs_persistence"][24] == 0.12
    assert sci["latest_depletion_fraction"] == 0.45
    assert sci["advisories_by_category"]["AGRONOMIC_RISK"] == 1
    assert sci["advisories_by_severity"]["WARNING"] == 1


# ============================================================================
# 4. MLOps Experiment Tracking Tests
# ============================================================================

def test_mlops_experiment_tracker_lineage_and_manifest():
    """Verify experiment lineage, Git SHA tracking, parameter/metric logging, and manifest export."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tracker = ExperimentTracker(runs_dir=tmpdir, backend="LOCAL_LEDGER")
        
        with tracker.start_run(
            run_id="EXP-TEST-001",
            experiment_id="EXP-20261002-TEST",
            dataset_name="USCRN_Lincoln_11_SW",
            dataset_version="2023_hourly",
            model_name="M2_EnvironmentalVector",
        ) as run_ctx:
            run_ctx.log_param("tau_risk", 0.70)
            run_ctx.log_param("root_depth_cm", 100.0)
            run_ctx.log_metrics({"mae_24h": 0.0082, "rmse_24h": 0.0115, "coverage_80_24h": 0.95})
            run_ctx.set_tag("phase", "Phase4_Operational")

        manifest_path = Path(tmpdir) / "EXP-TEST-001" / "manifest.json"
        assert manifest_path.exists()
        
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
            
        assert manifest_data["run_id"] == "EXP-TEST-001"
        assert manifest_data["experiment_id"] == "EXP-20261002-TEST"
        assert manifest_data["git_commit_sha"] != ""
        assert manifest_data["hyperparameters"]["tau_risk"] == 0.70
        assert manifest_data["metrics"]["mae_24h"] == 0.0082
        assert manifest_data["tags"]["phase"] == "Phase4_Operational"
        assert manifest_data["tags"]["status"] == "COMPLETED"


# ============================================================================
# 5. In-Memory Stream Broker Tests
# ============================================================================

def test_in_memory_stream_broker_pub_sub():
    """Verify In-Memory event broker pub-sub, filtering, consumer groups, and queue tracking."""
    broker = InMemoryStreamBroker()
    
    msg1_id = broker.publish("stream:telemetry", {"event_id": "evt-001", "temp": 21.5}, correlation_id="c1")
    msg2_id = broker.publish("stream:telemetry", {"event_id": "evt-002", "temp": 22.0}, correlation_id="c2")
    msg3_id = broker.publish("stream:alerts", {"alert_id": "alt-001", "level": "WARNING"}, correlation_id="c3")

    assert broker.get_stream_length("stream:telemetry") == 2
    assert broker.get_stream_length("stream:alerts") == 1

    # Consume batch
    batch = broker.consume("stream:telemetry", consumer_group="test_group", batch_size=10)
    assert len(batch) == 2
    assert batch[0].payload["event_id"] == "evt-001"
    assert batch[1].payload["event_id"] == "evt-002"
    assert batch[0].correlation_id == "c1"

    # Replay support
    replayed = broker.replay("stream:telemetry", from_index=0)
    assert len(replayed) == 2


# ============================================================================
# 6. Reliability & Fault Tolerance Tests
# ============================================================================

def test_dead_letter_queue_and_poison_pill():
    """Verify that malformed or unprocessable messages are routed to the DLQ with failure diagnostic."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dlq_file = Path(tmpdir) / "dlq.jsonl"
        dlq = DeadLetterQueue(dlq_file=dlq_file)
        
        poison_payload = {"invalid_json_structure": "###", "corrupted": True}
        item = dlq.push(
            payload=poison_payload,
            reason="JSONSchemaValidationError: Required field 'event_time' missing",
            exception=ValueError("Invalid field schema"),
        )

        assert dlq.count() == 1
        items = dlq.get_items()
        assert len(items) == 1
        assert "JSONSchemaValidationError" in items[0].failure_reason
        assert "Invalid field schema" in items[0].exception_details
        assert dlq_file.exists()


def test_event_deduplicator_idempotency():
    """Verify that duplicate event submissions within deduplication window are rejected idempotently."""
    dedup = EventDeduplicator(max_keys=100)
    
    key1 = dedup.compute_key(source_id="STATION_01", event_time="2023-06-01T12:00:00Z", site_id="FIELD_01")
    assert dedup.is_duplicate(key1) is False
    assert dedup.register(key1) is True

    # Duplicate registration
    assert dedup.is_duplicate(key1) is True
    assert dedup.register(key1) is False

    key2 = dedup.compute_key(source_id="STATION_01", event_time="2023-06-01T13:00:00Z", site_id="FIELD_01")
    assert dedup.is_duplicate(key2) is False
    assert dedup.register(key2) is True


def test_out_of_order_sequencer():
    """Verify that out-of-order incoming events are buffered and flushed in strict chronological order."""
    sequencer = OutOfOrderSequencer(window_size=10)
    
    t0_iso = "2023-05-01T10:00:00+00:00"
    t1_iso = "2023-05-01T11:00:00+00:00"
    t2_iso = "2023-05-01T12:00:00+00:00"
    t3_iso = "2023-05-01T13:00:00+00:00"

    # Ingest out of order: t2, t0, t3, t1
    sequencer.push({"id": "e2", "event_time": t2_iso})
    sequencer.push({"id": "e0", "event_time": t0_iso})
    sequencer.push({"id": "e3", "event_time": t3_iso})
    sequencer.push({"id": "e1", "event_time": t1_iso})

    assert sequencer.count() == 4
    flushed = sequencer.flush_sorted()
    assert len(flushed) == 4
    assert flushed[0]["id"] == "e0"
    assert flushed[1]["id"] == "e1"
    assert flushed[2]["id"] == "e2"
    assert flushed[3]["id"] == "e3"
    assert sequencer.count() == 0


def test_resilient_forecast_router_fallback():
    """Verify that when a primary advanced model fails, the router gracefully falls back to persistence."""
    class FailingPrimaryModel:
        def predict(self, current_vwc):
            raise RuntimeError("GPU/Inference Server Timeout")

    baseline = PersistenceModel(horizons=[1, 6, 12, 24])
    router = ResilientForecastRouter(primary_model=FailingPrimaryModel(), persistence_baseline=baseline)

    current_val = 0.285
    preds, used_fallback = router.predict_safe(current_vwc=current_val)

    assert used_fallback is True
    assert router.fallback_count == 1
    assert preds[1] == current_val
    assert preds[24] == current_val


# ============================================================================
# 7. Streaming Worker & End-to-End Operational Pipeline Tests
# ============================================================================

def _build_sample_telemetry_event(dt: datetime, vwc_val: float) -> TelemetryEvent:
    measurements = [
        TelemetryMeasurement(
            sensor_id=f"SOIL_VWC_{depth}CM",
            variable_name=VariableName.VOLUMETRIC_WATER_CONTENT,
            depth_cm=float(depth),
            value=vwc_val,
            unit=Unit.M3_M3,
            qc_flag=QCFlag.VALID,
        )
        for depth in [5, 10, 20, 50, 100]
    ] + [
        TelemetryMeasurement(
            sensor_id="AIR_TEMP_150CM",
            variable_name=VariableName.AIR_TEMPERATURE,
            depth_cm=0.0,
            value=22.0,
            unit=Unit.DEGC,
            qc_flag=QCFlag.VALID,
        ),
        TelemetryMeasurement(
            sensor_id="PRECIP_TOTAL",
            variable_name=VariableName.PRECIPITATION,
            depth_cm=0.0,
            value=0.0,
            unit=Unit.MM,
            qc_flag=QCFlag.VALID,
        ),
        TelemetryMeasurement(
            sensor_id="SOLAR_RAD",
            variable_name=VariableName.SOLAR_RADIATION,
            depth_cm=0.0,
            value=450.0,
            unit=Unit.W_M2,
            qc_flag=QCFlag.VALID,
        ),
    ]
    return TelemetryEvent.create_new(
        source_id="USCRN_NE_Lincoln_11_SW",
        site_id="FIELD_LINCOLN_01",
        event_time=dt,
        measurements=measurements,
        data_class=DataClass.OBSERVED,
        network="USCRN",
    )



def test_streaming_worker_pipeline_execution():
    """Verify stream worker consumes raw telemetry event, runs Tier1 QC, state building, forecasting, and emits to streams."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from agri_telemetry.storage.sqlite_store import SQLiteStore
        db_path = Path(tmpdir) / "stream_test.db"
        store = SQLiteStore(db_path=db_path)
        broker = InMemoryStreamBroker()
        
        worker = TelemetryStreamWorker(broker=broker, store=store)

        t0 = datetime(2023, 6, 1, 10, 0, tzinfo=timezone.utc)
        t1 = datetime(2023, 6, 1, 11, 0, tzinfo=timezone.utc)
        
        evt0 = _build_sample_telemetry_event(t0, 0.28)
        evt1 = _build_sample_telemetry_event(t1, 0.27)

        broker.publish("stream:telemetry", evt0.to_dict())
        broker.publish("stream:telemetry", evt1.to_dict())

        batch_result = worker.process_next_batch(batch_size=10)
        assert batch_result.processed_count == 2
        assert batch_result.valid_count == 2
        assert batch_result.forecasts_emitted == 2
        assert batch_result.errors_count == 0

        # Verify forecast stream received published events
        forecast_msgs = broker.consume("stream:forecasts", consumer_group="audit_group", batch_size=10)
        assert len(forecast_msgs) == 2

        worker.close()



def test_operational_pipeline_on_real_uscrn():
    """Verify operational pipeline running on Lincoln 2023 data sample."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "operational_test.db"
        runs_dir = Path(tmpdir) / "runs"
        
        config = AppConfig()
        config.storage.db_path = str(db_path)
        config.storage.runs_dir = str(runs_dir)
        
        pipeline = OperationalPipeline(config=config)
        
        data_file = Path("data/raw/CRNH0203-2023-NE_Lincoln_11_SW.txt")
        if data_file.exists():
            summary = pipeline.run_on_dataset(data_file=data_file, max_records=200)
            assert summary.total_records == 200
            assert summary.valid_events_count > 0
            assert summary.forecast_events_count > 0
            assert summary.persistence_mae[1] > 0.0
            
            # Verify MLOps manifest was written
            manifest_file = runs_dir / summary.run_id / "manifest.json"
            assert manifest_file.exists()
        
        pipeline.close()
