"""
Unit and integration tests for Phase 6: Operational Demonstration & Human Interface.
Verifies Dashboard API contracts, dynamic MAD calculations, uncertainty labels, fault isolation, and demo runner.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request
import urllib.error
import pytest

from agri_telemetry.ui.server import DashboardSession, DashboardServer
from agri_telemetry.simulation.demo_runner import Phase6DemoRunner


def test_dashboard_session_initialization_and_status_payload():
    """Validates session initialization, dynamic MAD threshold calculation, and uncertainty labeling."""
    session = DashboardSession()
    status = session.get_status_payload()

    # 1. Site and Provenance
    assert "site" in status
    site = status["site"]
    assert site["site_key"] == "SIMULATED_ESP32"
    assert site["is_simulated"] is True
    assert site["data_class"] == "SIMULATED_REPLAY"

    # 2. Dynamic Soil Parameters (Not hard-coded)
    assert "soil_params" in status
    soil = status["soil_params"]
    assert soil["theta_fc"] == 0.32
    assert soil["theta_wp"] == 0.14
    assert soil["mad_fraction"] == 0.50
    # Dynamically calculated: 0.32 - 0.50 * (0.32 - 0.14) = 0.230
    assert soil["theta_mad"] == 0.230

    # 3. Current State
    assert "current_state" in status
    cur = status["current_state"]
    assert 0.10 <= cur["theta_rz"] <= 0.40
    assert cur["qc_status"] == "VALID"

    # 4. Forecast Horizons and Horizon-Distinguished Uncertainty Labels
    assert "forecast" in status
    fcs = status["forecast"]
    assert len(fcs) == 7  # 1, 6, 12, 24, 48, 72, 168h

    for f in fcs:
        h = f["horizon_hours"]
        if h <= 48:
            assert "Partially Supported" in f["uncertainty_label"]
            assert f["is_research_uncertainty"] is False
        else:
            assert "Research" in f["uncertainty_label"]
            assert f["is_research_uncertainty"] is True

    # 5. Non-actuating Advisory Guarantee
    assert "advisory" in status
    adv = status["advisory"]
    assert adv["is_actuating"] is False


def test_dashboard_step_forward_advances_telemetry():
    """Validates advancing the stream by 1 hour updates the timestamp and observed history."""
    session = DashboardSession()
    t_pre = session.current_time
    n_pre = len(session.observed_history)

    res = session.step_forward(hours=1)
    assert res["status"] == "SUCCESS"
    assert session.current_time > t_pre
    assert len(session.observed_history) >= n_pre


def test_dashboard_spike_fault_injection_and_quarantine_isolation():
    """Validates that injected sensor spike is quarantined with NO agronomic alert emitted."""
    session = DashboardSession()
    res = session.inject_fault("spike")
    assert res["status"] == "QUARANTINED"
    assert session.is_last_quarantined is True

    status = session.get_status_payload()
    assert status["current_state"]["qc_status"] == "QUARANTINED"

    # Crucial assertion: No agronomic water risk advisory generated from quarantined synthetic spike
    if status["advisory"]["has_advisory"]:
        assert status["advisory"]["category"] != "AGRONOMIC_WATER_RISK"
        assert status["advisory"]["category"] == "DATA_QUALITY_ALERT"


def test_dashboard_duplicate_packet_suppression():
    """Validates that duplicate packet is discarded idempotently and increment counter."""
    session = DashboardSession()
    pre_dup = session.mqtt_adapter.duplicates_dropped

    # Ingest baseline packet
    session.step_forward(1)

    # Ingest duplicate
    res = session.inject_fault("duplicate")
    assert session.mqtt_adapter.duplicates_dropped > pre_dup


def test_dashboard_site_selection_updates_soil_parameters():
    """Validates selecting an independent USCRN station dynamically updates soil parameters."""
    session = DashboardSession()
    session.select_site("IL_Champaign_9_SW")

    status = session.get_status_payload()
    assert status["site"]["site_key"] == "IL_Champaign_9_SW"
    assert status["site"]["is_simulated"] is False
    assert status["site"]["data_class"] == "OBSERVED_IN_SITU"

    # Champaign soil params (FC: 0.34, WP: 0.14 -> MAD = 0.34 - 0.50*(0.20) = 0.240)
    assert status["soil_params"]["theta_fc"] == 0.34
    assert status["soil_params"]["theta_wp"] == 0.14
    assert status["soil_params"]["theta_mad"] == 0.240


def test_dashboard_http_server_and_api_endpoints():
    """Validates Dashboard HTTP server endpoints headlessly via urllib."""
    server = DashboardServer(host="127.0.0.1", port=8099)
    server.start(block=False)

    base_url = "http://127.0.0.1:8099"
    try:
        # GET /api/status
        req = urllib.request.urlopen(f"{base_url}/api/status")
        assert req.status == 200
        data = json.loads(req.read().decode("utf-8"))
        assert "current_state" in data
        assert "forecast" in data
        assert "advisory" in data

        # GET /api/sites
        req_sites = urllib.request.urlopen(f"{base_url}/api/sites")
        assert req_sites.status == 200
        sites = json.loads(req_sites.read().decode("utf-8"))
        assert len(sites) >= 5

        # POST /api/step
        step_req = urllib.request.Request(
            f"{base_url}/api/step",
            data=json.dumps({"hours": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        step_resp = urllib.request.urlopen(step_req)
        assert step_resp.status == 200
        step_data = json.loads(step_resp.read().decode("utf-8"))
        assert "current_state" in step_data

        # POST /api/inject-fault (spike)
        fault_req = urllib.request.Request(
            f"{base_url}/api/inject-fault",
            data=json.dumps({"fault_type": "spike"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        fault_resp = urllib.request.urlopen(fault_req)
        assert fault_resp.status == 200
        fault_data = json.loads(fault_resp.read().decode("utf-8"))
        assert fault_data["current_state"]["qc_status"] == "QUARANTINED"

    finally:
        server.stop()


def test_phase6_demo_runner_execution():
    """Validates automated execution of Phase 6 demonstration sequence and summary export."""
    runner = Phase6DemoRunner()
    report = runner.run_demonstration(save_report=True)

    assert report.total_steps == 5
    assert report.passed_steps == 5
    assert report.is_successful is True

    # Check generated summary file
    out_file = Path(__file__).parent.parent / "runs" / "phase6_demo_summary.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["is_successful"] is True
    assert len(data["step_results"]) == 5
    assert len(data["key_findings"]) >= 4
