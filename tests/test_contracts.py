"""
Unit Tests for Telemetry, Forecast, and Alert Event Contracts.
Verifies bidirectional compliance with Draft 2020-12 JSON schemas.
"""

import json
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from agri_telemetry.contracts import (
    TelemetryEvent,
    TelemetryMeasurement,
    ForecastEvent,
    HorizonPrediction,
    Quantiles,
    PredictionInterval80,
    AlertEvent,
    TriggerCondition,
    assert_valid_payload,
    validate_payload,
)
from agri_telemetry.domain.enums import (
    DataClass,
    VariableName,
    Unit,
    QCFlag,
    TargetVariable,
    AlertCategory,
    AlertSeverity,
    ThresholdType,
)


def test_telemetry_event_valid():
    now = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    measurements = [
        TelemetryMeasurement(
            sensor_id="SOIL_VWC_5CM",
            variable_name=VariableName.VOLUMETRIC_WATER_CONTENT,
            depth_cm=5.0,
            value=0.285,
            unit=Unit.M3_M3,
            qc_flag=QCFlag.VALID,
        ),
        TelemetryMeasurement(
            sensor_id="AIR_TEMP_150CM",
            variable_name=VariableName.AIR_TEMPERATURE,
            depth_cm=0.0,
            value=24.5,
            unit=Unit.DEGC,
            qc_flag=QCFlag.VALID,
        ),
    ]

    event = TelemetryEvent.create_new(
        source_id="USCRN_NE_Lincoln_11_SW",
        site_id="FIELD_NE_01",
        event_time=now,
        measurements=measurements,
        data_class=DataClass.OBSERVED,
        network="USCRN",
    )

    payload = event.to_dict()
    assert_valid_payload("telemetry", payload)
    assert event.natural_key is not None
    assert len(event.natural_key) == 64  # SHA256 hex


def test_forecast_event_valid():
    origin = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    predictions = [
        HorizonPrediction(
            horizon_hours=1,
            valid_time="2023-06-01T13:00:00Z",
            point_forecast=0.285,
            quantiles=Quantiles(q10=0.270, q25=0.280, q50=0.285, q75=0.290, q90=0.300),
            prediction_interval_80=PredictionInterval80(lower=0.270, upper=0.300),
            unit="m3/m3",
        ),
        HorizonPrediction(
            horizon_hours=24,
            valid_time="2023-06-02T12:00:00Z",
            point_forecast=0.275,
            quantiles=Quantiles(q10=0.250, q25=0.265, q50=0.275, q75=0.285, q90=0.305),
            prediction_interval_80=PredictionInterval80(lower=0.250, upper=0.305),
            unit="m3/m3",
        ),
    ]

    event = ForecastEvent.create_new(
        source_id="USCRN_NE_Lincoln_11_SW",
        site_id="FIELD_NE_01",
        forecast_origin_time=origin,
        target_variable=TargetVariable.VOLUMETRIC_WATER_CONTENT,
        model_name="PERSISTENCE_BASELINE",
        model_version="1.0.0",
        predictions=predictions,
        target_depth_range_cm=[0.0, 100.0],
        random_seed=42,
    )

    payload = event.to_dict()
    assert_valid_payload("forecast", payload)


def test_alert_event_valid():
    trigger_time = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    condition = TriggerCondition(
        threshold_type=ThresholdType.MANAGEMENT_ALLOWABLE_DEPLETION,
        threshold_value=0.50,
        threshold_unit="fraction",
        forecast_horizon_hours=24,
        exceedance_probability=0.82,
        predicted_value=0.54,
    )

    event = AlertEvent.create_new(
        category=AlertCategory.AGRONOMIC_RISK,
        severity=AlertSeverity.WARNING,
        source_id="USCRN_NE_Lincoln_11_SW",
        site_id="FIELD_NE_01",
        trigger_time=trigger_time,
        trigger_condition=condition,
        actionable_guidance="Root-zone soil moisture depletion predicted to exceed 50% MAD within 24 hours (P=0.82). Evaluate irrigation scheduling.",
    )

    payload = event.to_dict()
    assert_valid_payload("alert", payload)
    assert event.is_autonomous_actuation is False


def test_schema_rejection_on_invalid_data():
    # Test missing required field in TelemetryEvent
    invalid_payload = {
        "schema_version": "1.0.0",
        "source_id": "USCRN_NE_Lincoln_11_SW",
        # Missing event_id, site_id, etc.
    }
    is_valid, errors = validate_payload("telemetry", invalid_payload)
    assert not is_valid
    assert len(errors) > 0

    # Test autonomous_actuation cannot be True
    trigger_time = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    condition = TriggerCondition(
        threshold_type=ThresholdType.SENSOR_OUT_OF_RANGE,
        threshold_value=0.60,
    )
    # Pydantic should forbid setting is_autonomous_actuation to True
    with pytest.raises(ValidationError):
        AlertEvent(
            schema_version="1.0.0",
            alert_id="c0a80101-0000-0000-0000-000000000001",
            category=AlertCategory.DATA_QUALITY_ALERT,
            severity=AlertSeverity.CRITICAL,
            source_id="S1",
            site_id="F1",
            trigger_time="2023-06-01T12:00:00Z",
            trigger_condition=condition,
            actionable_guidance="Sensor value out of physical bounds.",
            is_autonomous_actuation=True,  # type: ignore
        )
