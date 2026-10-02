"""
Tests for Uncertainty Calibration, Horizon Partitioning, and NWP Value Investigation.
"""

import numpy as np
import pandas as pd
import pytest
from agri_telemetry.forecasting.uncertainty_calibration import (
    StaticQuantileCalibrator,
    HorizonDispersionCalibrator,
    RegimeConditionedCalibrator,
    PowerLawDispersionCalibrator,
    IntervalPrediction,
)
from agri_telemetry.experiments.uncertainty_experiments import Phase3ExperimentRunner


def test_static_quantile_calibrator_fitting():
    synthetic_series = [0.25 + 0.01 * np.sin(i / 12.0) for i in range(200)]
    cal = StaticQuantileCalibrator(horizons=[1, 6, 24])
    cal.fit(synthetic_series)

    assert cal._is_fitted
    pred = cal.predict_interval(point_forecast=0.25, horizon_hours=6, nominal_coverage=0.80)
    assert isinstance(pred, IntervalPrediction)
    assert pred.lower_bound <= pred.point_forecast <= pred.upper_bound
    assert pred.interval_width > 0.0


def test_horizon_dispersion_calibrator_mad_scaling():
    synthetic_series = [0.20 + 0.005 * i for i in range(100)]
    cal = HorizonDispersionCalibrator(horizons=[1, 12, 24], use_mad=True)
    cal.fit(synthetic_series)

    assert cal._is_fitted
    assert 1 in cal.scale_per_horizon
    assert 24 in cal.scale_per_horizon

    # 90% interval must be wider than 80% interval
    pred_80 = cal.predict_interval(point_forecast=0.25, horizon_hours=12, nominal_coverage=0.80)
    pred_90 = cal.predict_interval(point_forecast=0.25, horizon_hours=12, nominal_coverage=0.90)
    assert pred_90.interval_width > pred_80.interval_width


def test_regime_conditioned_calibrator_partitioning():
    n = 300
    series = [0.25 + 0.02 * (i % 10) for i in range(n)]
    met_df = pd.DataFrame({
        "precip_mm": [5.0 if i % 50 == 0 else 0.0 for i in range(n)],
        "solar_rad_wm2": [500.0 if (i % 24) in range(8, 18) else 0.0 for i in range(n)],
    })

    cal = RegimeConditionedCalibrator(horizons=[1, 6, 24])
    cal.fit(series, met_df=met_df)
    assert cal._is_fitted

    # Wet regime prediction
    pred_wet = cal.predict_interval(point_forecast=0.25, horizon_hours=6, precip_24h=10.0, solar_rad=100.0)
    assert pred_wet.regime_tag == "WET_ANTECEDENT"

    # High evap regime prediction
    pred_dry_solar = cal.predict_interval(point_forecast=0.25, horizon_hours=6, precip_24h=0.0, solar_rad=600.0)
    assert pred_dry_solar.regime_tag == "HIGH_EVAP"

    # Quiescent dry regime prediction
    pred_quiescent = cal.predict_interval(point_forecast=0.25, horizon_hours=6, precip_24h=0.0, solar_rad=0.0)
    assert pred_quiescent.regime_tag == "DRY_QUIESCENT"


def test_power_law_dispersion_calibrator():
    np.random.seed(42)
    # Synthetic diffusion series where std grows with sqrt(h)
    series = list(np.cumsum(np.random.normal(0, 0.001, 500)) + 0.25)
    cal = PowerLawDispersionCalibrator(horizons=[1, 6, 24, 72, 168])
    cal.fit(series)

    assert cal._is_fitted
    pred_1 = cal.predict_interval(point_forecast=0.25, horizon_hours=1, nominal_coverage=0.80)
    pred_168 = cal.predict_interval(point_forecast=0.25, horizon_hours=168, nominal_coverage=0.80)
    assert pred_168.interval_width > pred_1.interval_width


def test_phase3_horizon_partitioned_execution():
    runner = Phase3ExperimentRunner()
    res = runner.run_horizon_partitioned_evaluation()
    assert res.target_name == "root_zone_vwc"
    assert 1 in res.metrics_by_horizon
    assert 168 in res.metrics_by_horizon
    assert res.metrics_by_horizon[1]["assigned_model"] == "M2_ENVIRONMENTAL_ARX"
    assert res.metrics_by_horizon[168]["assigned_model"] == "M1_AUTOREGRESSIVE"


def test_phase3_future_weather_nwp_investigation():
    runner = Phase3ExperimentRunner()
    res = runner.run_future_weather_nwp_investigation()
    assert res.target_name == "root_zone_vwc"
    assert 24 in res.metrics_by_horizon
    # Oracle NWP with perfect future rain knowledge should have lower or equal RMSE than past-only ARX
    m_24 = res.metrics_by_horizon[24]
    assert m_24["rmse_nwp_oracle"] <= m_24["rmse_past_arx"] + 1e-4
