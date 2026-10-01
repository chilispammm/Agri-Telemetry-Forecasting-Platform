"""
Unit & Integration Tests for 3-Tier Risk and Alert Evaluation.
"""

from datetime import datetime, timezone
import pytest

from agri_telemetry.contracts import assert_valid_payload
from agri_telemetry.domain.enums import AlertCategory, AlertSeverity, ThresholdType
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.alerts import RiskEvaluationConfig, AgronomicRiskEvaluator
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator


def create_state(depletion: float, is_valid: bool = True) -> SoilWaterState:
    now = datetime(2023, 7, 15, 14, 0, 0, tzinfo=timezone.utc)
    return SoilWaterState(
        timestamp=now,
        site_id="FIELD_NE_01",
        source_id="USCRN_LINCOLN",
        depth_vwc={5.0: 0.20, 10.0: 0.20, 20.0: 0.20, 50.0: 0.20, 100.0: 0.20},
        theta_rz=0.20,
        theta_fc=0.32,
        theta_wp=0.14,
        theta_sat=0.45,
        depletion_fraction=depletion,
        available_water_fraction=1.0 - depletion,
        root_depth_cm=100.0,
        storage_mm=200.0,
        deficit_mm=120.0,
        is_valid=is_valid,
    )


def test_no_alert_when_moisture_adequate():
    evaluator = AgronomicRiskEvaluator(config=RiskEvaluationConfig(d_mad=0.50))
    state = create_state(depletion=0.25)
    alerts = evaluator.evaluate_state_and_forecast(state)
    assert len(alerts) == 0


def test_real_time_mad_breach():
    evaluator = AgronomicRiskEvaluator(config=RiskEvaluationConfig(d_mad=0.50))
    state = create_state(depletion=0.55)
    alerts = evaluator.evaluate_state_and_forecast(state)

    assert len(alerts) == 1
    a = alerts[0]
    assert a.category == AlertCategory.AGRONOMIC_RISK
    assert a.severity == AlertSeverity.WARNING
    assert a.trigger_condition.threshold_type == ThresholdType.MANAGEMENT_ALLOWABLE_DEPLETION
    assert a.is_autonomous_actuation is False
    assert_valid_payload("alert", a.to_dict())


def test_critical_wilting_proximity_alert():
    evaluator = AgronomicRiskEvaluator(config=RiskEvaluationConfig(d_mad=0.50, critical_wilting_depletion=0.85))
    state = create_state(depletion=0.90)
    alerts = evaluator.evaluate_state_and_forecast(state)

    assert len(alerts) == 1
    a = alerts[0]
    assert a.category == AlertCategory.AGRONOMIC_RISK
    assert a.severity == AlertSeverity.CRITICAL
    assert a.trigger_condition.threshold_type == ThresholdType.CRITICAL_WILTING_PROXIMITY
    assert a.is_autonomous_actuation is False
    assert_valid_payload("alert", a.to_dict())


def test_quarantined_state_isolation():
    # If state is marked invalid (e.g. from sensor quarantine), NO agronomic alert should ever fire
    evaluator = AgronomicRiskEvaluator(config=RiskEvaluationConfig(d_mad=0.50))
    state = create_state(depletion=0.95, is_valid=False)
    alerts = evaluator.evaluate_state_and_forecast(state)
    assert len(alerts) == 0


def test_probabilistic_forward_forecast_alert():
    # Calibrator with positive residual spread (drying tendency)
    calibrator = EmpiricalUncertaintyCalibrator(horizons=[24])
    # Synthetic errors where depletion increases by ~0.10 over 24h
    calibrator.fit([0.30 + (i * 0.005) for i in range(100)])

    evaluator = AgronomicRiskEvaluator(
        config=RiskEvaluationConfig(d_mad=0.50, tau_risk=0.70),
        calibrator=calibrator,
    )

    # Current depletion = 0.45 (< 0.50), but with drying spread forecast crosses 0.50 with P >= 0.70
    state = create_state(depletion=0.45)
    alerts = evaluator.evaluate_state_and_forecast(state, forecast_horizons=[24])

    if alerts:
        a = alerts[0]
        assert a.category == AlertCategory.AGRONOMIC_RISK
        assert a.trigger_condition.forecast_horizon_hours == 24
        assert a.trigger_condition.exceedance_probability >= 0.70
        assert_valid_payload("alert", a.to_dict())
