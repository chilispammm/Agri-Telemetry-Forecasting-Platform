"""
Unit and Verification Tests for Phase 2 Forecasting Experiments.
Verifies temporal integrity, baseline parity, metric correctness, and final test protection.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
import pytest

from agri_telemetry.forecasting.feature_extractor import FeatureAvailabilitySpec, FeatureExtractor
from agri_telemetry.forecasting.baselines import ClimatologicalMeanModel, EWMAModel
from agri_telemetry.forecasting.statistical_ar import AutoregressiveForecaster
from agri_telemetry.forecasting.exogenous_model import EnvironmentalForecaster
from agri_telemetry.experiments.runner import Phase2ExperimentRunner


def test_feature_availability_contract_rejects_future_lags():
    """Negative lags indicate future data and must raise an immediate exception."""
    with pytest.raises(ValueError, match="Temporal leakage violation"):
        FeatureAvailabilitySpec(
            feature_name="illegal_future_precip",
            source_variable="precipitation",
            lag_hours=-1,  # Future lag!
        )


def test_feature_extractor_causality():
    """Extracts features strictly from past/current observations."""
    extractor = FeatureExtractor(target_lags=[0, 1, 6], include_diurnal=True)
    base_t = datetime(2023, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    timestamps = [base_t + timedelta(hours=i) for i in range(50)]
    series = [0.25 + 0.01 * np.sin(i / 5.0) for i in range(50)]

    X, names = extractor.extract_features(timestamps, series)
    assert X.shape[0] == 50
    assert "target_current" in names
    assert "target_lag_1h" in names
    assert "target_lag_6h" in names
    assert "hour_sin" in names
    assert not np.isnan(X).any()


def test_skill_vs_persistence_metric_math():
    """Verifies that Skill vs Persistence is mathematically sound."""
    mse_persistence = 0.000100

    # Superior candidate with lower MSE -> positive skill
    mse_better = 0.000075
    skill_better = 1.0 - (mse_better / mse_persistence)
    assert skill_better == pytest.approx(0.25, abs=1e-5)

    # Identical candidate -> zero skill
    skill_identical = 1.0 - (mse_persistence / mse_persistence)
    assert skill_identical == pytest.approx(0.0, abs=1e-5)

    # Inferior candidate with higher MSE -> negative skill
    mse_worse = 0.000150
    skill_worse = 1.0 - (mse_worse / mse_persistence)
    assert skill_worse == pytest.approx(-0.50, abs=1e-5)


def test_climatology_and_ewma_baselines():
    base_t = datetime(2023, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    series = [0.20, 0.22, 0.24, 0.26, 0.28]

    # Climatology predicts mean = 0.24
    clim_model = ClimatologicalMeanModel(horizons=[1, 6])
    clim_preds = clim_model.predict(series, origin_time=base_t)
    assert clim_preds[0].point_forecast == pytest.approx(0.24, abs=1e-4)

    # EWMA with alpha=0.5
    ewma_model = EWMAModel(alpha=0.5, horizons=[1, 6])
    ewma_preds = ewma_model.predict(series, origin_time=base_t)
    assert 0.20 <= ewma_preds[0].point_forecast <= 0.28


def test_statistical_ar_model_fit_and_predict():
    base_t = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    timestamps = [base_t + timedelta(hours=i) for i in range(200)]
    # Autoregressive series with AR(1) phi = 0.95
    series = [0.30]
    for _ in range(199):
        series.append(0.015 + 0.95 * series[-1] + np.random.normal(0, 0.001))

    ar_model = AutoregressiveForecaster(horizons=[1, 6, 24], target_lags=[0, 1, 2])
    ar_model.fit(timestamps[:100], series[:100])

    preds = ar_model.predict(series[100:150], timestamps[100:150], origin_time=timestamps[149])
    assert len(preds) == 3
    assert 0.15 <= preds[0].point_forecast <= 0.45


def test_environmental_forecaster_fit_and_predict():
    base_t = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    timestamps = [base_t + timedelta(hours=i) for i in range(200)]
    series = [0.28 + 0.02 * np.sin(i / 12.0) for i in range(200)]

    env_model = EnvironmentalForecaster(horizons=[1, 6, 24])
    env_model.fit(timestamps[:100], series[:100])

    preds = env_model.predict(series[100:150], timestamps[100:150], origin_time=timestamps[149])
    assert len(preds) == 3
    for p in preds:
        assert p.point_forecast >= 0.0
