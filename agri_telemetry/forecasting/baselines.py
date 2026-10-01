"""
Baseline Reference Models for Phase 2 Forecasting Ladder.
- B0: Persistence Benchmark (in persistence.py)
- B1: Climatological / Historical Cumulative Mean Model
- B2: EWMA / Rolling Mean Baseline Model
"""

from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np

from agri_telemetry.domain.models import ForecastHorizonPrediction
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator


class ClimatologicalMeanModel:
    """
    B1 Baseline: Predicts historical cumulative mean of observations prior to forecast origin.
    Equation: Y_hat_{t+h|t} = mean(Y_{1:t})
    """

    def __init__(
        self,
        horizons: Optional[List[int]] = None,
        calibrator: Optional[EmpiricalUncertaintyCalibrator] = None,
        model_name: str = "CLIMATOLOGICAL_MEAN",
        model_version: str = "1.0.0",
    ):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.calibrator = calibrator
        self.model_name = model_name
        self.model_version = model_version

    def predict(
        self,
        historical_series: List[float],
        origin_time: datetime,
        unit: str = "m3/m3",
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> List[ForecastHorizonPrediction]:
        """
        Generates predictions equal to historical cumulative sample mean up to time t.
        """
        valid_vals = [v for v in historical_series if v is not None and not np.isnan(v)]
        if not valid_vals:
            mean_val = (min_bound + max_bound) / 2.0
        else:
            mean_val = float(np.mean(valid_vals))

        predictions: List[ForecastHorizonPrediction] = []
        for h in self.horizons:
            valid_dt = origin_time + timedelta(hours=h)
            point = float(np.clip(mean_val, min_bound, max_bound))

            if self.calibrator and self.calibrator.is_calibrated:
                quantiles = self.calibrator.calculate_quantiles(
                    point_forecast=point,
                    horizon_hours=h,
                    min_bound=min_bound,
                    max_bound=max_bound,
                )
                pi_lower = quantiles["q10"]
                pi_upper = quantiles["q90"]
            else:
                quantiles = {"q10": point, "q25": point, "q50": point, "q75": point, "q90": point}
                pi_lower = point
                pi_upper = point

            predictions.append(
                ForecastHorizonPrediction(
                    horizon_hours=h,
                    target_time=valid_dt,
                    point_forecast=point,
                    unit=unit,
                    q10=quantiles["q10"],
                    q25=quantiles["q25"],
                    q50=quantiles["q50"],
                    q75=quantiles["q75"],
                    q90=quantiles["q90"],
                    pi_lower_80=pi_lower,
                    pi_upper_80=pi_upper,
                )
            )
        return predictions


class EWMAModel:
    """
    B2 Baseline: Exponentially Weighted Moving Average (EWMA) level predictor.
    Level estimate: S_t = alpha * Y_t + (1 - alpha) * S_{t-1}
    Forecast: Y_hat_{t+h|t} = S_t
    """

    def __init__(
        self,
        alpha: float = 0.20,
        horizons: Optional[List[int]] = None,
        calibrator: Optional[EmpiricalUncertaintyCalibrator] = None,
        model_name: str = "EWMA_BASELINE",
        model_version: str = "1.0.0",
    ):
        self.alpha = alpha
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.calibrator = calibrator
        self.model_name = model_name
        self.model_version = model_version

    def predict(
        self,
        historical_series: List[float],
        origin_time: datetime,
        unit: str = "m3/m3",
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> List[ForecastHorizonPrediction]:
        """
        Computes EWMA level from historical series up to time t and emits flat forecasts.
        """
        valid_vals = [v for v in historical_series if v is not None and not np.isnan(v)]
        if not valid_vals:
            ewma_val = (min_bound + max_bound) / 2.0
        else:
            # Recursive EWMA calculation
            s = valid_vals[0]
            for val in valid_vals[1:]:
                s = self.alpha * val + (1.0 - self.alpha) * s
            ewma_val = s

        predictions: List[ForecastHorizonPrediction] = []
        for h in self.horizons:
            valid_dt = origin_time + timedelta(hours=h)
            point = float(np.clip(ewma_val, min_bound, max_bound))

            if self.calibrator and self.calibrator.is_calibrated:
                quantiles = self.calibrator.calculate_quantiles(
                    point_forecast=point,
                    horizon_hours=h,
                    min_bound=min_bound,
                    max_bound=max_bound,
                )
                pi_lower = quantiles["q10"]
                pi_upper = quantiles["q90"]
            else:
                quantiles = {"q10": point, "q25": point, "q50": point, "q75": point, "q90": point}
                pi_lower = point
                pi_upper = point

            predictions.append(
                ForecastHorizonPrediction(
                    horizon_hours=h,
                    target_time=valid_dt,
                    point_forecast=point,
                    unit=unit,
                    q10=quantiles["q10"],
                    q25=quantiles["q25"],
                    q50=quantiles["q50"],
                    q75=quantiles["q75"],
                    q90=quantiles["q90"],
                    pi_lower_80=pi_lower,
                    pi_upper_80=pi_upper,
                )
            )
        return predictions
