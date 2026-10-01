"""
Unit & Integration Tests for Tier-1 Quality Control & Quarantine Engine.
"""

from datetime import datetime, timezone, timedelta
import pytest

from agri_telemetry.contracts import TelemetryEvent, TelemetryMeasurement, assert_valid_payload
from agri_telemetry.domain.enums import (
    DataClass,
    VariableName,
    Unit,
    QCFlag,
    AlertCategory,
    AlertSeverity,
)
from agri_telemetry.qc import (
    check_physical_range,
    check_vwc_spike,
    check_stuck_sensor,
    Tier1QCEngine,
    QuarantineBuffer,
)


def test_physical_range_bounds():
    # Valid soil VWC
    assert check_physical_range(VariableName.VOLUMETRIC_WATER_CONTENT, 0.25) == QCFlag.VALID
    # Out of bounds (> 0.60)
    assert check_physical_range(VariableName.VOLUMETRIC_WATER_CONTENT, 0.85) == QCFlag.OUT_OF_RANGE
    # Out of bounds (< 0.00)
    assert check_physical_range(VariableName.VOLUMETRIC_WATER_CONTENT, -0.05) == QCFlag.OUT_OF_RANGE
    # Missing value
    assert check_physical_range(VariableName.VOLUMETRIC_WATER_CONTENT, None) == QCFlag.MISSING

    # Temperature bounds
    assert check_physical_range(VariableName.AIR_TEMPERATURE, 22.0) == QCFlag.VALID
    assert check_physical_range(VariableName.AIR_TEMPERATURE, 85.0) == QCFlag.OUT_OF_RANGE


def test_vwc_spike_detection():
    # Gradual drying: 0.30 -> 0.28 (delta = 0.02) without rain -> VALID
    assert check_vwc_spike(0.28, 0.30, precipitation_mm=0.0) == QCFlag.VALID

    # Impossible jump: 0.20 -> 0.40 (delta = 0.20) WITHOUT rain -> SUSPECT_SPIKE
    assert check_vwc_spike(0.40, 0.20, precipitation_mm=0.0) == QCFlag.SUSPECT_SPIKE

    # Rapid infiltration jump: 0.20 -> 0.40 WITH 15mm precipitation -> VALID
    assert check_vwc_spike(0.40, 0.20, precipitation_mm=15.0) == QCFlag.VALID


def test_stuck_sensor_detection():
    # 11 constant values -> not yet flagged
    hist_11 = [0.255] * 11
    assert check_stuck_sensor(hist_11, min_stuck_hours=12) == QCFlag.VALID

    # 12 constant values -> SUSPECT_STUCK
    hist_12 = [0.255] * 12
    assert check_stuck_sensor(hist_12, min_stuck_hours=12) == QCFlag.SUSPECT_STUCK


def test_qc_engine_processing_and_quarantine():
    buffer = QuarantineBuffer()
    qc_engine = Tier1QCEngine(quarantine_buffer=buffer, stuck_window_hours=12)

    base_time = datetime(2023, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Clean event
    clean_event = TelemetryEvent.create_new(
        source_id="STATION_01",
        site_id="FIELD_A",
        event_time=base_time,
        measurements=[
            TelemetryMeasurement(
                sensor_id="SOIL_VWC_5CM",
                variable_name=VariableName.VOLUMETRIC_WATER_CONTENT,
                depth_cm=5.0,
                value=0.28,
                unit=Unit.M3_M3,
            ),
            TelemetryMeasurement(
                sensor_id="MET_PRECIP",
                variable_name=VariableName.PRECIPITATION,
                depth_cm=0.0,
                value=0.0,
                unit=Unit.MM,
            ),
        ],
    )

    ev_clean, is_quarantined_1, alert_1 = qc_engine.evaluate_event(clean_event)
    assert not is_quarantined_1
    assert alert_1 is None
    assert ev_clean.qc_summary.quarantined is False
    assert buffer.count() == 0

    # 2. Corrupted event (VWC = 0.95, breaching physical limit of 0.60)
    bad_time = base_time + timedelta(hours=1)
    bad_event = TelemetryEvent.create_new(
        source_id="STATION_01",
        site_id="FIELD_A",
        event_time=bad_time,
        measurements=[
            TelemetryMeasurement(
                sensor_id="SOIL_VWC_5CM",
                variable_name=VariableName.VOLUMETRIC_WATER_CONTENT,
                depth_cm=5.0,
                value=0.95,  # Unphysical
                unit=Unit.M3_M3,
            ),
            TelemetryMeasurement(
                sensor_id="MET_PRECIP",
                variable_name=VariableName.PRECIPITATION,
                depth_cm=0.0,
                value=0.0,
                unit=Unit.MM,
            ),
        ],
    )

    ev_bad, is_quarantined_2, alert_2 = qc_engine.evaluate_event(bad_event)
    assert is_quarantined_2
    assert alert_2 is not None
    assert alert_2.category == AlertCategory.DATA_QUALITY_ALERT
    assert alert_2.severity == AlertSeverity.CRITICAL
    assert alert_2.is_autonomous_actuation is False
    assert buffer.count() == 1

    # Validate emitted alert against Draft 2020-12 schema
    assert_valid_payload("alert", alert_2.to_dict())
