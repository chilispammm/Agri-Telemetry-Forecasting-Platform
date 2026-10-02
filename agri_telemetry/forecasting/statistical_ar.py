"""
Statistical Autoregressive (AR) Time-Series Forecasting Model.
Direct multi-horizon linear autoregressive model with L2 regularization.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np

from agri_telemetry.domain.models import ForecastHorizonPrediction
from agri_telemetry.forecasting.feature_extractor import FeatureExtractor
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator


class AutoregressiveForecaster:
    """
    Direct Multi-Horizon Autoregressive Model.
    For each horizon h in [1, 6, 12, 24, 48, 72, 168]:
        Y_hat_{t+h|t} = beta_{0,h} + beta_{1,h} * Y_t + beta_{2,h} * Y_{t-1} + ...
    Fitted via regularized least-squares on historical training data strictly prior to test split.
    """

    def __init__(
        self,
        horizons: Optional[List[int]] = None,
        target_lags: Optional[List[int]] = None,
        ridge_alpha: float = 1.0,
        calibrator: Optional[EmpiricalUncertaintyCalibrator] = None,
        model_name: str = "AUTOREGRESSIVE_DIRECT",
        model_version: str = "1.0.0",
    ):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.target_lags = target_lags or [0, 1, 2, 6, 12, 24, 48]
        self.ridge_alpha = ridge_alpha
        self.calibrator = calibrator
        self.model_name = model_name
        self.model_version = model_version

        self.extractor = FeatureExtractor(
            target_lags=self.target_lags,
            include_precip=False,
            include_temp=False,
            include_solar=False,
            include_diurnal=False,
        )

        # Fitted regression weights per horizon: {h: (weights, bias)}
        self._models: Dict[int, Tuple[np.ndarray, float]] = {}
        self._is_fitted = False

    def fit(
        self,
        timestamps: List[datetime],
        target_series: List[float],
    ) -> "AutoregressiveForecaster":
        """
        Fits direct autoregressive coefficients on training series.
        """
        n = len(target_series)
        X, _ = self.extractor.extract_features(timestamps, target_series)
        y = np.array(target_series, dtype=float)

        self._models.clear()
        train_residuals: Dict[int, List[float]] = {h: [] for h in self.horizons}

        for h in self.horizons:
            if n <= h + 50:
                continue

            # Target at t+h
            X_train = X[: n - h]
            y_train = y[h: n]

            valid_mask = ~(np.isnan(X_train).any(axis=1) | np.isnan(y_train))
            X_clean = X_train[valid_mask]
            y_clean = y_train[valid_mask]

            if len(y_clean) < 50:
                continue

            # Standardize and solve with Ridge regression: w = (X^T X + alpha*I)^(-1) X^T y
            # Add intercept column
            X_design = np.hstack([np.ones((len(X_clean), 1)), X_clean])
            reg_matrix = self.ridge_alpha * np.eye(X_design.shape[1])
            reg_matrix[0, 0] = 0.0  # Do not regularize intercept

            try:
                w = np.linalg.solve(X_design.T @ X_design + reg_matrix, X_design.T @ y_clean)
                bias = float(w[0])
                weights = w[1:]
                self._models[h] = (weights, bias)

                # Collect in-sample residuals for uncertainty calibration
                preds_train = X_design @ w
                resids = list(y_clean - preds_train)
                train_residuals[h] = resids
            except np.linalg.LinAlgError:
                # Fallback to persistence weights (1.0 on lag 0, 0 elsewhere)
                w_persist = np.zeros(X_clean.shape[1])
                w_persist[0] = 1.0
                self._models[h] = (w_persist, 0.0)

        # Calibrate prediction intervals using model-specific residuals
        cal = EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        cal._residuals = train_residuals
        cal._compute_stats()
        cal._is_calibrated = True
        self.calibrator = cal

        self._is_fitted = True
        return self

    def predict_from_feature_vector(
        self,
        x_t: np.ndarray,
        origin_time: datetime,
        current_val: float,
        unit: str = "m3/m3",
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> List[ForecastHorizonPrediction]:
        predictions: List[ForecastHorizonPrediction] = []
        for h in self.horizons:
            valid_dt = origin_time + timedelta(hours=h)
            if h in self._models:
                weights, bias = self._models[h]
                raw_pred = float(np.dot(x_t, weights) + bias)
            else:
                raw_pred = float(current_val)

            point = float(np.clip(raw_pred, min_bound, max_bound))
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

    def predict_vectorized(
        self,
        X_test: np.ndarray,
        horizon: int,
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> np.ndarray:
        """
        Fast vectorized prediction for a matrix of test feature rows.
        """
        if horizon not in self._models:
            return np.clip(X_test[:, 0], min_bound, max_bound)
        weights, bias = self._models[horizon]
        raw_preds = X_test @ weights + bias
        return np.clip(raw_preds, min_bound, max_bound)

    def predict(
        self,
        recent_target_series: List[float],
        recent_timestamps: List[datetime],
        origin_time: datetime,
        unit: str = "m3/m3",
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> List[ForecastHorizonPrediction]:
        X_all, _ = self.extractor.extract_features(recent_timestamps, recent_target_series)
        x_t = X_all[-1]
        cur_v = recent_target_series[-1] if recent_target_series else 0.25
        return self.predict_from_feature_vector(x_t, origin_time, cur_v, unit, min_bound, max_bound)

