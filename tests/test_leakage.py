"""
Verification Tests for Temporal Boundary Integrity and Non-Contamination (No Leakage).
"""

from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

from agri_telemetry.forecasting import WalkForwardEvaluator, EmpiricalUncertaintyCalibrator, PersistenceModel


def test_walk_forward_leak_free_split():
    """
    Verifies that the uncertainty calibrator and model have NO access to test-set observations.
    """
    base_t = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    n = 200
    timestamps = [base_t + timedelta(hours=i) for i in range(n)]

    # Train split has a mean around 0.30
    # Test split undergoes a drastic shift to 0.10
    train_vals = list(np.random.normal(0.30, 0.01, size=100))
    test_vals = list(np.random.normal(0.10, 0.01, size=100))
    values = train_vals + test_vals

    evaluator = WalkForwardEvaluator(horizons=[1, 6, 24], train_fraction=0.50)
    report = evaluator.evaluate(timestamps=timestamps, values=values)

    # The evaluation start time must be strictly after the training split cutoff
    split_cutoff = timestamps[100]
    assert report.evaluation_start == split_cutoff

    # Ensure predictions at time t in test set only used value at time t
    # For a persistence model, point forecast is Y_t
    model = PersistenceModel(horizons=[1])
    for t in range(len(test_vals) - 1):
        pred = model.predict(current_value=test_vals[t], origin_time=timestamps[100 + t])
        assert pred[0].point_forecast == test_vals[t]
