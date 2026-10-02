"""
Unit and integration tests for Phase 5: Multi-Site Generalisation, External Validation,
and MQTT Telemetry Integration.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import pytest

from agri_telemetry.data.site_registry import (
    STATION_REGISTRY,
    SiteSuitability,
    ClimateRegime,
    get_active_evaluation_sites,
    get_all_registered_sites,
    get_station_metadata,
)
from agri_telemetry.simulation.esp32_simulator import (
    ESP32TelemetrySimulator,
    ESP32SensorReading,
)
from agri_telemetry.streaming.mqtt_adapter import (
    MQTTTelemetryIngestAdapter,
    MQTTMessage,
)
from agri_telemetry.streaming.broker import InMemoryStreamBroker
from agri_telemetry.reliability.recovery import (
    DeadLetterQueue,
    EventDeduplicator,
    OutOfOrderSequencer,
)
from agri_telemetry.domain.enums import DataClass, VariableName, QCFlag
from agri_telemetry.experiments.robustness_analysis import (
    RobustnessAnalyzer,
    PacketLossStressResult,
    ResequencingStressResult,
    SeasonalFailureAnalysis,
)
from agri_telemetry.experiments.multisite_evaluation import (
    MultiSiteEvaluator,
    SingleSiteEvaluationResult,
    MultiSiteEvaluationReport,
)


def test_site_registry_and_metadata_catalog():
    """Validates station registry metadata, inclusion rationale, and exclusion catalog."""
    all_sites = get_all_registered_sites()
    assert len(all_sites) >= 8, f"Expected at least 8 registered sites, got {len(all_sites)}"

    eval_sites = get_active_evaluation_sites()
    assert len(eval_sites) >= 4, f"Expected at least 4 evaluation sites, got {len(eval_sites)}"

    # Check baseline presence
    baseline = get_station_metadata("NE_Lincoln_11_SW")
    assert baseline is not None
    assert baseline.suitability == SiteSuitability.CANONICAL_BASELINE
    assert len(baseline.probe_depths_cm) == 5

    # Check independent site
    champaign = get_station_metadata("IL_Champaign_9_SW")
    assert champaign is not None
    assert champaign.suitability == SiteSuitability.INDEPENDENT_EVALUATION
    assert champaign.climate_regime == ClimateRegime.MIDWEST_CORN_BELT
    assert champaign.probe_completeness_pct > 95.0

    # Check excluded site with rationale
    austin = get_station_metadata("TX_Austin_33_NW")
    assert austin is not None
    assert austin.suitability == SiteSuitability.EXCLUDED_INCOMPLETE_PROBES
    assert austin.exclusion_reason is not None
    assert "20cm" in austin.exclusion_reason


def test_esp32_simulator_packet_generation_and_simulation_labels():
    """Validates ESP32 simulator payload structure and strict simulation labelling."""
    simulator = ESP32TelemetrySimulator(
        device_id="ESP32-UNIT-01",
        site_id="FIELD_TEST_SIM",
        base_theta=0.28,
        random_seed=123,
    )
    t0 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    packet = simulator.generate_packet(event_time=t0)

    assert packet["device_id"] == "ESP32-UNIT-01"
    assert packet["site_id"] == "FIELD_TEST_SIM"
    assert packet["seq"] == 1
    assert packet["timestamp_utc"] == "2026-06-01T12:00:00Z"
    assert packet["is_simulated"] is True  # Strict simulation label
    assert "sensors" in packet
    sensors = packet["sensors"]
    assert "soil_moisture_10cm" in sensors
    assert 0.05 <= sensors["soil_moisture_10cm"] <= 0.50
    assert "solar_radiation_wm2" in sensors
    assert "air_temp_c" in sensors

    # Anomaly injection tests
    spike_pkt = simulator.generate_packet(inject_spike=True)
    assert spike_pkt["sensors"]["soil_moisture_10cm"] == 0.88

    nan_pkt = simulator.generate_packet(inject_nan=True)
    assert nan_pkt["sensors"]["soil_moisture_10cm"] is None

    # Stream generator
    stream = list(simulator.generate_stream(start_time=t0, hours=5))
    assert len(stream) == 5
    assert stream[0]["seq"] < stream[-1]["seq"]


def test_mqtt_adapter_ingress_normalisation_and_dlq():
    """Validates MQTT adapter parsing, schema normalisation, DLQ routing, and simulation flags."""
    broker = InMemoryStreamBroker()
    dlq = DeadLetterQueue()
    dedup = EventDeduplicator()
    sequencer = OutOfOrderSequencer()

    adapter = MQTTTelemetryIngestAdapter(
        broker=broker,
        telemetry_stream="test:telemetry",
        dlq=dlq,
        deduplicator=dedup,
        sequencer=sequencer,
    )

    # 1. Valid simulated packet
    sim = ESP32TelemetrySimulator(device_id="ESP32-ADAPTER-TEST", random_seed=42)
    pkt = sim.generate_packet()
    payload_bytes = json.dumps(pkt).encode("utf-8")

    msg_id = adapter.on_message("agri/field/telemetry", payload_bytes)
    assert msg_id is not None
    assert adapter.messages_received == 1
    assert adapter.events_published == 1
    assert adapter.dlq_quarantined == 0

    # Verify event stored in broker stream
    stream_events = broker.consume("test:telemetry", batch_size=10)
    assert len(stream_events) == 1
    event_dict = stream_events[0].payload
    assert event_dict["source_id"] == "ESP32-ADAPTER-TEST"
    assert event_dict["provenance"]["data_class"] == DataClass.SIMULATED_REPLAY.value
    assert event_dict["provenance"]["network"] == "ESP32_MQTT_SIMULATED"

    # 2. Corrupt / invalid JSON -> DLQ
    corrupt_bytes = b"NOT_VALID_JSON{{"
    dlq_id = adapter.on_message("agri/field/telemetry", corrupt_bytes)
    assert dlq_id is None
    assert adapter.dlq_quarantined == 1
    assert dlq.count() == 1
    failures = dlq.get_items()
    assert "Invalid JSON" in failures[0].failure_reason

    # 3. Missing required fields -> DLQ
    incomplete_bytes = json.dumps({"foo": "bar"}).encode("utf-8")
    adapter.on_message("agri/field/telemetry", incomplete_bytes)
    assert adapter.dlq_quarantined == 2
    assert dlq.count() == 2


def test_mqtt_adapter_deduplication():
    """Validates idempotent duplicate suppression on MQTT ingress."""
    broker = InMemoryStreamBroker()
    dedup = EventDeduplicator()
    adapter = MQTTTelemetryIngestAdapter(broker=broker, deduplicator=dedup)

    sim = ESP32TelemetrySimulator(device_id="ESP32-DEDUP-TEST", random_seed=99)
    t_fixed = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
    pkt = sim.generate_packet(event_time=t_fixed)
    payload_bytes = json.dumps(pkt).encode("utf-8")

    # First receipt: accepted
    id1 = adapter.on_message("agri/field/telemetry", payload_bytes)
    assert id1 is not None
    assert adapter.events_published == 1
    assert adapter.duplicates_dropped == 0

    # Duplicate receipt with identical source_id and timestamp: dropped
    id2 = adapter.on_message("agri/field/telemetry", payload_bytes)
    assert id2 is None
    assert adapter.events_published == 1
    assert adapter.duplicates_dropped == 1


def test_robustness_packet_loss_and_resequencing():
    """Validates stress testing logic for packet loss and out-of-order resequencing."""
    analyzer = RobustnessAnalyzer()

    # Out of order resequencing stress test
    reseq_res = analyzer.run_resequencing_stress_test(n_packets=100, out_of_order_fraction=0.25)
    assert reseq_res.total_packets == 100
    assert reseq_res.out_of_order_injected > 0
    assert reseq_res.residual_disorder_count == 0
    assert reseq_res.resequencing_success_rate == 100.0


def test_multisite_validation_report_structure_and_values():
    """Validates the structure and empirical metrics of the multi-site evaluation report."""
    report_path = Path(__file__).parent.parent / "runs" / "multisite_validation_report.json"
    assert report_path.exists(), f"Report file not found at {report_path}"

    report_data = json.loads(report_path.read_text(encoding="utf-8"))
    assert "site_results" in report_data
    assert "cross_site_summary" in report_data

    stations = report_data["site_results"]
    assert len(stations) >= 5

    # Check Champaign 9 SW (Midwest Corn Belt transfer)
    champaign = stations["IL_Champaign_9_SW"]
    assert champaign["mean_mae_skill_1_48h"] > 0.0
    assert champaign["generalisation_outcome"] == "PARTIALLY_SUPPORTED"

    # Check Watkinsville 5 SSE (Subtropical failure mode)
    watkinsville = stations["GA_Watkinsville_5_SSE"]
    assert watkinsville["mean_mae_skill_1_48h"] < 0.0  # Demonstrates convective storm degradation
    assert watkinsville["generalisation_outcome"] == "DEGRADED"

    # Check Las Cruces 20 N (Arid Desert)
    las_cruces = stations["NM_Las_Cruces_20_N"]
    assert las_cruces["generalisation_outcome"] == "PARTIALLY_SUPPORTED"


def test_robustness_report_file_structure():
    """Validates the generated robustness report on disk."""
    report_path = Path(__file__).parent.parent / "runs" / "robustness_report.json"
    assert report_path.exists(), f"Robustness report not found at {report_path}"

    report_data = json.loads(report_path.read_text(encoding="utf-8"))
    assert "packet_loss_results" in report_data
    assert "resequencing_results" in report_data
    assert "seasonal_results" in report_data
    assert len(report_data["boundary_findings"]) >= 5
