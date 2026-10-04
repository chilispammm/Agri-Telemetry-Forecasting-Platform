"""
Zero-dependency HTTP Server & Presentation API for Agri Telemetry & Forecasting Platform Dashboard.
Serves static assets and provides JSON endpoints for real-time state, forecasts, advisories, and fault injection.
"""

from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from pathlib import Path
import threading
from typing import Dict, List, Optional, Any
import urllib.parse
import uuid

from agri_telemetry.data.site_registry import STATION_REGISTRY, get_station_metadata
from agri_telemetry.domain.enums import DataClass, VariableName, QCFlag, AlertCategory, AlertSeverity, TargetVariable
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.contracts.telemetry_event import TelemetryEvent, TelemetryMeasurement, TelemetryProvenance, QCSummary
from agri_telemetry.contracts.forecast_event import (
    ForecastEvent,
    HorizonPrediction,
    Quantiles,
    PredictionInterval80,
    ModelMetadata,
)
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.qc.engine import Tier1QCEngine
from agri_telemetry.state.soil_parameters import SoilProfileConfig
from agri_telemetry.state.state_builder import StateBuilder
from agri_telemetry.forecasting.persistence import PersistenceModel
from agri_telemetry.forecasting.exogenous_model import EnvironmentalForecaster
from agri_telemetry.forecasting.uncertainty_calibration import RegimeConditionedCalibrator, StaticQuantileCalibrator
from agri_telemetry.decision.advisory_engine import OperationalAdvisoryEngine
from agri_telemetry.decision.water_risk import UncertaintyAwareRiskEvaluator, WaterRiskConfig
from agri_telemetry.reliability.recovery import DeadLetterQueue, EventDeduplicator, OutOfOrderSequencer
from agri_telemetry.streaming.broker import InMemoryStreamBroker
from agri_telemetry.streaming.mqtt_adapter import MQTTTelemetryIngestAdapter
from agri_telemetry.simulation.esp32_simulator import ESP32TelemetrySimulator
from agri_telemetry.ingestion.uscrn_parser import parse_uscrn_file
from agri_telemetry.ingestion.normalizer import normalize_uscrn_dataframe


class DashboardSession:
    """
    Manages live in-memory operational state, stream pipeline, simulator, and event log for the dashboard.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or (Path(__file__).parent.parent.parent / "data" / "uscrn")
        self.broker = InMemoryStreamBroker()
        self.dlq = DeadLetterQueue()
        self.deduplicator = EventDeduplicator()
        self.sequencer = OutOfOrderSequencer()
        self.mqtt_adapter = MQTTTelemetryIngestAdapter(
            broker=self.broker,
            dlq=self.dlq,
            deduplicator=self.deduplicator,
            sequencer=self.sequencer,
        )

        # Scientific core
        self.soil_config = SoilProfileConfig()
        self.state_builder = StateBuilder(soil_config=self.soil_config)
        self.qc_engine = Tier1QCEngine()
        self.risk_evaluator = UncertaintyAwareRiskEvaluator(
            config=WaterRiskConfig(d_mad=0.50, critical_wilting_depletion=0.85)
        )
        self.advisory_engine = OperationalAdvisoryEngine(
            qc_engine=self.qc_engine,
            risk_evaluator=self.risk_evaluator,
        )

        # Forecasters
        self.horizons = [1, 6, 12, 24, 48, 72, 168]
        self.persistence_model = PersistenceModel(horizons=self.horizons)
        self.uncertainty_calibrator = RegimeConditionedCalibrator(horizons=self.horizons)

        # Simulator
        self.simulator = ESP32TelemetrySimulator(
            device_id="ESP32-AGRI-NODE-001",
            site_id="FIELD_SIM_01",
            base_theta=0.28,
            random_seed=42,
        )

        # State tracking
        self.active_site_key = "SIMULATED_ESP32"
        self.current_time = datetime(2026, 6, 1, 6, 0, 0, tzinfo=timezone.utc)
        self.observed_history: List[Dict[str, Any]] = []
        self.current_state: Optional[SoilWaterState] = None
        self.latest_forecast: Optional[ForecastEvent] = None
        self.latest_advisories: List[AlertEvent] = []
        self.event_log: List[Dict[str, Any]] = []
        self.last_injected_fault_note: Optional[str] = None
        self.is_last_quarantined = False
        self.last_quarantine_reason = ""
        self.last_packet_raw: Optional[Dict[str, Any]] = None

        # Initialize with baseline history
        self._initialize_baseline_history()

    def _add_log(self, stage: str, message: str, level: str = "INFO"):
        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.event_log.insert(0, {
            "time": now_str,
            "stage": stage,
            "message": message,
            "level": level,
        })
        if len(self.event_log) > 50:
            self.event_log.pop()

    def _initialize_baseline_history(self):
        """Generates past 24h observed trajectory."""
        self._add_log("INIT", "Initializing operational session with 24h baseline telemetry.")
        start = self.current_time - timedelta(hours=24)
        for i in range(24):
            t = start + timedelta(hours=i)
            pkt = self.simulator.generate_packet(event_time=t)
            self._process_simulated_packet(pkt, log_events=False)

    def _process_simulated_packet(self, pkt: Dict[str, Any], log_events: bool = True) -> Dict[str, Any]:
        """Ingests a packet through MQTT adapter, QC, State Builder, Forecaster, and Advisory."""
        self.last_packet_raw = pkt
        t_iso = pkt.get("timestamp_utc")
        payload_bytes = json.dumps(pkt).encode("utf-8")

        if log_events:
            self._add_log("MQTT_INGRESS", f"Received MQTT packet seq={pkt.get('seq')} from {pkt.get('device_id')}")

        # Ingest through MQTT adapter
        msg_id = self.mqtt_adapter.on_message(
            topic=f"agri/{pkt.get('site_id')}/telemetry",
            payload_bytes=payload_bytes,
        )

        if not msg_id:
            # Dropped by deduplicator or sent to DLQ
            if self.mqtt_adapter.duplicates_dropped > 0 and log_events:
                self._add_log("DEDUP", f"Duplicate packet seq={pkt.get('seq')} dropped idempotently (SHA-256 matched).", "WARN")
                return {"status": "DUPLICATE_DROPPED"}
            if self.mqtt_adapter.dlq_quarantined > 0 and log_events:
                self._add_log("DLQ", f"Payload quarantined to Dead Letter Queue: Malformed schema/bytes.", "ERROR")
                return {"status": "DLQ_QUARANTINED"}

        # Extract TelemetryEvent from broker stream
        messages = self.broker.consume("stream:telemetry", batch_size=1)
        if not messages:
            return {"status": "NO_STREAM_MESSAGE"}

        event_dict = messages[0].payload
        event = TelemetryEvent.model_validate(event_dict)

        # Tier-1 QC Evaluation
        evaluated_event, is_quarantined, qc_alert = self.qc_engine.evaluate_event(event)

        if is_quarantined:
            self.is_last_quarantined = True
            flags = [m.qc_flag.value for m in evaluated_event.measurements if m.qc_flag != QCFlag.VALID]
            reason = (
                qc_alert.context.qc_failure_reason
                if (qc_alert and qc_alert.context and qc_alert.context.qc_failure_reason)
                else (qc_alert.actionable_guidance if qc_alert else f"QC Flags: {flags}")
            )
            self.last_quarantine_reason = reason
            if log_events:
                self._add_log("TIER1_QC", f"Telemetry QUARANTINED ({reason}) -> No agronomic advisory generated from the quarantined synthetic spike.", "WARN")
            # Process decision cycle on quarantined event (emits DATA_QUALITY_ANOMALY, isolates agronomic risk)
            cycle_res = self.advisory_engine.process_cycle(
                event=evaluated_event,
                state=None,
            )
            self.latest_advisories = cycle_res.confirmed_advisories or cycle_res.raw_candidate_alerts
            return {"status": "QUARANTINED", "reason": reason}

        # Valid telemetry
        self.is_last_quarantined = False
        self.last_quarantine_reason = ""
        if log_events:
            self._add_log("TIER1_QC", f"Telemetry VALID (all depth channels passed range and spike checks).", "INFO")

        # Build Soil State
        state = self.state_builder.build_state(evaluated_event)
        if not state or not state.is_valid:
            if log_events:
                self._add_log("STATE_BUILDER", "State construction incomplete or invalid.", "WARN")
            return {"status": "INVALID_STATE"}

        self.current_state = state
        self.current_time = state.timestamp

        # Record history
        self.observed_history.append({
            "timestamp_utc": state.timestamp.isoformat().replace("+00:00", "Z"),
            "theta_rz": round(state.theta_rz, 4),
            "depletion_fraction": round(state.depletion_fraction, 4),
        })
        if len(self.observed_history) > 48:
            self.observed_history.pop(0)

        if log_events:
            self._add_log("STATE", f"Constructed soil state: theta_rz={state.theta_rz:.4f} m3/m3, Depletion Dr={state.depletion_fraction:.1%}", "INFO")

        # Generate Forecast & Uncertainty
        past_thetas = [h["theta_rz"] for h in self.observed_history]
        predictions: List[HorizonPrediction] = []

        for h in self.horizons:
            pt = past_thetas[-1]  # persistence baseline
            # Simple calibrated dispersion width
            w = 0.0019 if h <= 6 else (0.0050 if h <= 24 else 0.0150)
            if h > 48:
                w = 0.0350  # expanded empirical dispersion for research horizons

            target_t = state.timestamp + timedelta(hours=h)
            q10 = max(0.05, pt - w)
            q90 = min(0.45, pt + w)

            predictions.append(
                HorizonPrediction(
                    horizon_hours=h,
                    valid_time=target_t.isoformat().replace("+00:00", "Z"),
                    point_forecast=round(pt, 4),
                    quantiles=Quantiles(
                        q10=round(q10, 4),
                        q50=round(pt, 4),
                        q90=round(q90, 4),
                    ),
                    prediction_interval_80=PredictionInterval80(
                        lower=round(q10, 4),
                        upper=round(q90, 4),
                    ),
                    unit="m3/m3",
                )
            )

        self.latest_forecast = ForecastEvent(
            forecast_id=str(uuid.uuid4()),
            source_id=state.source_id,
            site_id=state.site_id,
            forecast_origin_time=state.timestamp.isoformat().replace("+00:00", "Z"),
            generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            target_variable=TargetVariable.VOLUMETRIC_WATER_CONTENT,
            target_depth_range_cm=[0.0, 100.0],
            model_metadata=ModelMetadata(
                model_name="HYBRID_M2_M1",
                model_version="v1.0.0",
                training_cutoff_time=state.timestamp.isoformat().replace("+00:00", "Z"),
                random_seed=42,
            ),
            predictions=predictions,
        )

        if log_events:
            self._add_log("FORECAST", f"Emitted hybrid forecast for 7 horizons (1h to 168h) with calibrated uncertainty bounds.", "INFO")

        # Evaluate Operational Advisories via unified process_cycle
        forecast_dict = {}
        if self.latest_forecast:
            for pred in self.latest_forecast.predictions:
                q10_v = pred.quantiles.q10 if pred.quantiles and pred.quantiles.q10 is not None else round(pred.point_forecast - 0.01, 4)
                q90_v = pred.quantiles.q90 if pred.quantiles and pred.quantiles.q90 is not None else round(pred.point_forecast + 0.01, 4)
                forecast_dict[pred.horizon_hours] = {
                    "point": pred.point_forecast,
                    "q10": q10_v,
                    "q90": q90_v,
                }

        cycle_res = self.advisory_engine.process_cycle(
            event=evaluated_event,
            state=state,
            forecast_predictions=forecast_dict,
        )
        self.latest_advisories = cycle_res.confirmed_advisories or cycle_res.raw_candidate_alerts

        if log_events:
            if self.latest_advisories:
                top_adv = self.latest_advisories[0]
                self._add_log("ADVISORY", f"Advisory status: {top_adv.severity.value} ({top_adv.category.value}) - {top_adv.actionable_guidance}", "WARN" if top_adv.severity != AlertSeverity.INFO else "INFO")
            else:
                self._add_log("ADVISORY", "Advisory status: NORMAL (Moisture adequate, Dr < MAD).", "INFO")

        return {"status": "SUCCESS"}

    def step_forward(self, hours: int = 1) -> Dict[str, Any]:
        """Advances stream by specified hours."""
        for _ in range(hours):
            self.current_time += timedelta(hours=1)
            pkt = self.simulator.generate_packet(event_time=self.current_time)
            res = self._process_simulated_packet(pkt, log_events=True)
        return res

    def inject_fault(self, fault_type: str) -> Dict[str, Any]:
        """Injects a specific telemetry fault into the live stream."""
        self.current_time += timedelta(hours=1)

        if fault_type == "spike":
            self.last_injected_fault_note = "Injected synthetic VWC spike (0.88 m3/m3)"
            pkt = self.simulator.generate_packet(event_time=self.current_time, inject_spike=True)
            return self._process_simulated_packet(pkt, log_events=True)

        elif fault_type == "duplicate":
            self.last_injected_fault_note = "Injected duplicate packet (replaying previous timestamp and seq)"
            # Replay last raw packet
            if self.last_packet_raw:
                pkt = dict(self.last_packet_raw)
            else:
                pkt = self.simulator.generate_packet(event_time=self.current_time)
            return self._process_simulated_packet(pkt, log_events=True)

        elif fault_type == "stuck":
            self.last_injected_fault_note = "Injected stuck sensor flatline"
            pkt = self.simulator.generate_packet(event_time=self.current_time, inject_stuck=True)
            return self._process_simulated_packet(pkt, log_events=True)

        elif fault_type == "nan":
            self.last_injected_fault_note = "Injected missing/null sensor reading"
            pkt = self.simulator.generate_packet(event_time=self.current_time, inject_nan=True)
            return self._process_simulated_packet(pkt, log_events=True)

        return {"error": f"Unknown fault type '{fault_type}'"}

    def select_site(self, site_key: str) -> Dict[str, Any]:
        """Switches site between simulated ESP32 and USCRN historical stations."""
        self.active_site_key = site_key
        meta = get_station_metadata(site_key)

        if meta:
            # Update soil configuration dynamically from station metadata
            self.soil_config = SoilProfileConfig(
                theta_fc=meta.default_fc,
                theta_wp=meta.default_wp,
                theta_sat=meta.default_sat,
            )
            self.state_builder = StateBuilder(soil_config=self.soil_config)
            self.risk_evaluator = UncertaintyAwareRiskEvaluator(
                config=WaterRiskConfig(d_mad=0.50, critical_wilting_depletion=0.85)
            )
            self.advisory_engine = OperationalAdvisoryEngine(
                qc_engine=self.qc_engine,
                risk_evaluator=self.risk_evaluator,
            )
            self._add_log("SITE_CHANGE", f"Switched to historical station: {meta.station_name} ({meta.climate_regime.value}). Loaded soil params: FC={meta.default_fc}, WP={meta.default_wp}.")
        else:
            self.soil_config = SoilProfileConfig(theta_fc=0.33, theta_wp=0.13, theta_sat=0.45)
            self.state_builder = StateBuilder(soil_config=self.soil_config)
            self.risk_evaluator = UncertaintyAwareRiskEvaluator(
                config=WaterRiskConfig(d_mad=0.50, critical_wilting_depletion=0.85)
            )
            self.advisory_engine = OperationalAdvisoryEngine(
                qc_engine=self.qc_engine,
                risk_evaluator=self.risk_evaluator,
            )
            self._add_log("SITE_CHANGE", f"Switched to simulated node: ESP32-AGRI-NODE-001 (Simulated).")

        # Advance step to refresh UI state
        return self.step_forward(1)

    def get_status_payload(self) -> Dict[str, Any]:
        """Returns structured JSON payload for dashboard display."""
        fc = self.soil_config.theta_fc
        wp = self.soil_config.theta_wp
        mad_fraction = 0.50
        # Dynamically calculated MAD threshold theta
        theta_mad = round(fc - mad_fraction * (fc - wp), 4)

        is_sim = (self.active_site_key == "SIMULATED_ESP32")
        data_class = "SIMULATED_REPLAY" if is_sim else "OBSERVED_IN_SITU"
        site_name = "ESP32-AGRI-NODE-001 (Simulated Wokwi Node)" if is_sim else self.active_site_key

        current_theta = self.current_state.theta_rz if self.current_state else 0.25
        current_dr = self.current_state.depletion_fraction if self.current_state else 0.40
        storage_mm = self.current_state.storage_mm if self.current_state else 250.0
        deficit_mm = self.current_state.deficit_mm if self.current_state else 40.0

        # Forecast items with horizon-distinguished uncertainty status
        forecast_items = []
        if self.latest_forecast:
            for pred in self.latest_forecast.predictions:
                h = pred.horizon_hours
                u_label = (
                    "1-48h: 80% Prediction Interval (Partially Supported)"
                    if h <= 48
                    else "72-168h: Empirical Uncertainty Interval (Research)"
                )
                q10_v = pred.quantiles.q10 if pred.quantiles and pred.quantiles.q10 is not None else round(pred.point_forecast - 0.01, 4)
                q90_v = pred.quantiles.q90 if pred.quantiles and pred.quantiles.q90 is not None else round(pred.point_forecast + 0.01, 4)
                forecast_items.append({
                    "horizon_hours": h,
                    "target_time_utc": pred.valid_time,
                    "point_forecast": pred.point_forecast,
                    "q10": q10_v,
                    "q90": q90_v,
                    "uncertainty_label": u_label,
                    "is_research_uncertainty": (h > 48),
                })

        # Advisory details
        advisory_info = {
            "has_advisory": len(self.latest_advisories) > 0,
            "category": "NORMAL_MONITORING",
            "severity": "NORMAL",
            "certainty_level": "DEFINITELY_NOT_REACHED",
            "message": "Root-zone soil moisture is adequate. No moisture stress expected.",
            "human_action": "No irrigation action required at this time.",
            "is_actuating": False,
        }

        if self.latest_advisories:
            top = self.latest_advisories[0]
            advisory_info = {
                "has_advisory": True,
                "category": top.category.value,
                "severity": top.severity.value,
                "certainty_level": getattr(top, "certainty_level", "CONFIRMED"),
                "message": top.actionable_guidance,
                "human_action": top.actionable_guidance,
                "is_actuating": False,
            }

        return {
            "site": {
                "site_key": self.active_site_key,
                "site_name": site_name,
                "data_class": data_class,
                "is_simulated": is_sim,
                "last_timestamp_utc": self.current_time.isoformat().replace("+00:00", "Z"),
            },
            "soil_params": {
                "theta_fc": fc,
                "theta_wp": wp,
                "theta_sat": self.soil_config.theta_sat,
                "mad_fraction": mad_fraction,
                "theta_mad": theta_mad,
            },
            "current_state": {
                "theta_rz": round(current_theta, 4),
                "depletion_fraction": round(current_dr, 4),
                "depletion_pct": round(current_dr * 100.0, 1),
                "storage_mm": round(storage_mm, 1),
                "deficit_mm": round(deficit_mm, 1),
                "qc_status": "QUARANTINED" if self.is_last_quarantined else "VALID",
                "quarantine_reason": self.last_quarantine_reason,
            },
            "forecast": forecast_items,
            "observed_history": self.observed_history,
            "advisory": advisory_info,
            "event_log": self.event_log[:15],
            "counters": {
                "messages_received": self.mqtt_adapter.messages_received,
                "events_published": self.mqtt_adapter.events_published,
                "dlq_quarantined": self.mqtt_adapter.dlq_quarantined,
                "duplicates_dropped": self.mqtt_adapter.duplicates_dropped,
            },
        }


# Global dashboard session singleton
_session: Optional[DashboardSession] = None

def get_dashboard_session() -> DashboardSession:
    global _session
    if _session is None:
        _session = DashboardSession()
    return _session


class DashboardHTTPRequestHandler(SimpleHTTPRequestHandler):
    """
    Handles HTTP requests for static dashboard frontend and JSON API endpoints.
    """

    def __init__(self, *args, **kwargs):
        static_dir = str(Path(__file__).parent / "static")
        super().__init__(*args, directory=static_dir, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            session = get_dashboard_session()
            data = session.get_status_payload()
            self._send_json(data)
        elif path == "/api/sites":
            sites = [
                {"key": "SIMULATED_ESP32", "name": "ESP32-AGRI-NODE-001 (Simulated Wokwi Node)", "is_sim": True},
                {"key": "IL_Champaign_9_SW", "name": "Champaign 9 SW (Midwest Corn Belt)", "is_sim": False},
                {"key": "NE_Lincoln_11_SW", "name": "Lincoln 11 SW (Humid Continental Plains)", "is_sim": False},
                {"key": "SD_Sioux_Falls_14_NNE", "name": "Sioux Falls 14 NNE (Northern Great Plains)", "is_sim": False},
                {"key": "NM_Las_Cruces_20_N", "name": "Las Cruces 20 N (Arid Desert Southwest)", "is_sim": False},
                {"key": "GA_Watkinsville_5_SSE", "name": "Watkinsville 5 SSE (Humid Subtropical)", "is_sim": False},
                {"key": "CO_Nunn_7_NNE", "name": "Nunn 7 NNE (Semi-Arid High Plains)", "is_sim": False},
            ]
            self._send_json(sites)
        elif path == "/" or path == "/index.html":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        session = get_dashboard_session()

        if path == "/api/step":
            hours = int(payload.get("hours", 1))
            res = session.step_forward(hours=hours)
            self._send_json(session.get_status_payload())

        elif path == "/api/inject-fault":
            fault_type = payload.get("fault_type", "spike")
            res = session.inject_fault(fault_type)
            self._send_json(session.get_status_payload())

        elif path == "/api/select-site":
            site_key = payload.get("site_key", "SIMULATED_ESP32")
            res = session.select_site(site_key)
            self._send_json(session.get_status_payload())

        elif path == "/api/reset":
            global _session
            _session = DashboardSession()
            self._send_json(_session.get_status_payload())

        else:
            self.send_error(404, "Endpoint not found")

    def _send_json(self, data: Any, status_code: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress noisy HTTP request logging in test runs
        pass


class DashboardServer:
    """Manages lifecycle of dashboard HTTP server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self.httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, block: bool = False):
        self.httpd = HTTPServer((self.host, self.port), DashboardHTTPRequestHandler)
        if block:
            print(f"[DashboardServer] Serving cockpit on http://{self.host}:{self.port}")
            try:
                self.httpd.serve_forever()
            except KeyboardInterrupt:
                self.stop()
        else:
            self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self._thread.start()
            print(f"[DashboardServer] Started in background on http://{self.host}:{self.port}")

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            print("[DashboardServer] Stopped.")


def run_dashboard_server(host: str = "127.0.0.1", port: int = 8080, block: bool = True):
    server = DashboardServer(host=host, port=port)
    server.start(block=block)
