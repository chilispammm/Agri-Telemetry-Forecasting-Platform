"""
Unit & Integration Tests for Persistence Model, Uncertainty Calibration, and Forecasting Engine.
"""

from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

from agri_telemetry.contracts import assert_valid_payload
from agri_telemetry.domain.enums import TargetVariable
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.forecasting import (
    PersistenceModel,
    EmpiricalUncertaintyCalibrator,
    WalkForwardEvaluator,
    ForecastingEngine,
)


def test_persistence_model_predictions():
    now = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    model = PersistenceModel(horizons=[1, 6, 24, 48])
    
    preds = model.predict(current_value=0.275, origin_time=now, unit="m3/m3")
    assert len(preds) == 4
    for p in preds:
        assert p.point_forecast == pytest.approx(0.275, abs=1e-5)
        assert p.target_time == now + timedelta(hours=p.horizon_hours)


def test_uncertainty_calibrator_quantiles():
    # Synthetic drying time-series: slowly decaying with noise
    np.random.seed(42)
    t = np.linspace(0, 100, 500)
    series = 0.30 - 0.05 * (t / 100) + np.random.normal(0, 0.005, size=500)

    calibrator = EmpiricalUncertaintyCalibrator(horizons=[1, 6, 24])
    calibrator.fit(list(series))

    assert calibrator.is_calibrated is True
    stats_24 = calibrator.get_stats(24)
    assert stats_24 is not None
    assert stats_24.sample_size > 400
    assert stats_24.q10 < stats_24.q50 < stats_24.q90

    # Test exceedance probability
    p_cross = calibrator.estimate_exceedance_probability(point_forecast=0.30, horizon_hours=24, threshold_value=0.25)
    assert 0.0 <= p_cross <= 1.0


def test_walk_forward_evaluator():
    np.random.seed(42)
    base_t = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    timestamps = [base_t + timedelta(hours=i) for i in range(1000)]
    # Random walk with mean reversion
    values = [0.28]
    for _ in range(999):
        next_v = values[-1] + np.random.normal(-0.0001, 0.002)
        values.append(float(np.clip(next_v, 0.15, 0.40)))

    evaluator = WalkForwardEvaluator(horizons=[1, 6, 24], train_fraction=0.5)
    report = evaluator.evaluate(timestamps=timestamps, values=values)

    assert report.model_name == "PERSISTENCE_BASELINE"
    assert len(report.horizon_metrics) == 3
    
    # Check metrics
    m1 = report.horizon_metrics[1]
    m24 = report.horizon_metrics[24]
    # Error should grow with horizon
    assert m1.mae < m24.mae
    assert m1.rmse < m24.rmse
    # Coverage should be reasonably close to nominal 80%
    assert 0.65 <= m24.coverage_80 <= 0.95

    md_table = report.to_markdown_table()
    assert "Out-of-Sample Verification" in md_table


def test_forecasting_engine_and_contract_validation():
    now = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    state = SoilWaterState(
        timestamp=now,
        site_id="FIELD_01",
        source_id="STATION_01",
        depth_vwc={5.0: 0.28, 10.0: 0.28, 20.0: 0.27, 50.0: 0.25, 100.0: 0.22},
        theta_rz=0.26,
        theta_fc=0.32,
        theta_wp=0.14,
        theta_sat=0.45,
        depletion_fraction=0.333,
        available_water_fraction=0.667,
        root_depth_cm=100.0,
        storage_mm=260.0,
        deficit_mm=60.0,
        is_valid=True,
    )

    engine = ForecastingEngine(horizons=[1, 6, 12, 24])
    # Fit calibrator on a short synthetic series
    calibrator = EmpiricalUncertaintyCalibrator(horizons=[1, 6, 12, 24])
    calibrator.fit([0.26 + np.sin(i / 10.0) * 0.02 for i in range(100)])
    engine.calibrator = calibrator
    engine.model.calibrator = calibrator

    forecast_event = engine.generate_forecast(
        state=state,
        target_variable=TargetVariable.VOLUMETRIC_WATER_CONTENT,
    )

    assert len(forecast_event.predictions) == 4
    # Validate against JSON schema
    payload = forecast_event.to_dict()
    assert_valid_payload("forecast", payload)
