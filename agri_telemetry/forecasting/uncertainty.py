"""
Empirical Uncertainty Calibrator.
Computes empirical residual quantiles and prediction intervals from walk-forward errors.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np


@dataclass
class HorizonResidualStats:
    horizon_hours: int
    sample_size: int
    mean_error: float
    std_error: float
    q10: float
    q25: float
    q50: float
    q75: float
    q90: float


class EmpiricalUncertaintyCalibrator:
    """
    Fits and stores empirical residual distributions e_h = Y_{t+h} - Y_t per horizon.
    Produces calibrated prediction intervals and threshold exceedance probabilities.
    """

    def __init__(self, horizons: Optional[List[int]] = None):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        # Raw residuals: {horizon: [e_1, e_2, ...]}
        self._residuals: Dict[int, List[float]] = {h: [] for h in self.horizons}
        self._stats: Dict[int, HorizonResidualStats] = {}
        self._is_calibrated = False

    def fit(self, time_series: List[float]) -> "EmpiricalUncertaintyCalibrator":
        """
        Calculates all walk-forward persistence residuals: e_{t,h} = Y_{t+h} - Y_t.
        """
        n = len(time_series)
        self._residuals = {h: [] for h in self.horizons}

        for h in self.horizons:
            if n > h:
                for t in range(n - h):
                    y_t = time_series[t]
                    y_target = time_series[t + h]
                    if y_t is not None and y_target is not None and not (np.isnan(y_t) or np.isnan(y_target)):
                        err = float(y_target - y_t)
                        self._residuals[h].append(err)

        self._compute_stats()
        self._is_calibrated = True
        return self

    def _compute_stats(self) -> None:
        """Calculates empirical quantiles per horizon."""
        self._stats.clear()
        for h, errs in self._residuals.items():
            if not errs:
                # Default zero-spread fallback if insufficient data
                self._stats[h] = HorizonResidualStats(
                    horizon_hours=h,
                    sample_size=0,
                    mean_error=0.0,
                    std_error=0.0,
                    q10=0.0,
                    q25=0.0,
                    q50=0.0,
                    q75=0.0,
                    q90=0.0,
                )
                continue

            arr = np.array(errs)
            self._stats[h] = HorizonResidualStats(
                horizon_hours=h,
                sample_size=len(arr),
                mean_error=float(np.mean(arr)),
                std_error=float(np.std(arr)),
                q10=float(np.percentile(arr, 10)),
                q25=float(np.percentile(arr, 25)),
                q50=float(np.percentile(arr, 50)),
                q75=float(np.percentile(arr, 75)),
                q90=float(np.percentile(arr, 90)),
            )

    def get_stats(self, horizon_hours: int) -> Optional[HorizonResidualStats]:
        return self._stats.get(horizon_hours)

    def calculate_quantiles(
        self,
        point_forecast: float,
        horizon_hours: int,
        min_bound: float = 0.0,
        max_bound: float = 1.0,
    ) -> Dict[str, float]:
        """Returns bounded forecast quantiles: q_p = clip(point_forecast + delta_q_p)."""
        stats = self._stats.get(horizon_hours)
        if not stats:
            return {
                "q10": point_forecast,
                "q25": point_forecast,
                "q50": point_forecast,
                "q75": point_forecast,
                "q90": point_forecast,
            }

        return {
            "q10": float(np.clip(point_forecast + stats.q10, min_bound, max_bound)),
            "q25": float(np.clip(point_forecast + stats.q25, min_bound, max_bound)),
            "q50": float(np.clip(point_forecast + stats.q50, min_bound, max_bound)),
            "q75": float(np.clip(point_forecast + stats.q75, min_bound, max_bound)),
            "q90": float(np.clip(point_forecast + stats.q90, min_bound, max_bound)),
        }

    def estimate_exceedance_probability(
        self,
        point_forecast: float,
        horizon_hours: int,
        threshold_value: float,
    ) -> float:
        """
        Estimates empirical probability P(Y_{t+h} > threshold_value).
        """
        errs = self._residuals.get(horizon_hours, [])
        if not errs:
            return 1.0 if point_forecast >= threshold_value else 0.0

        arr = np.array(errs)
        simulated_values = point_forecast + arr
        exceedances = np.sum(simulated_values >= threshold_value)
        return float(exceedances / len(arr))

    @property
    def is_calibrated(self) -> bool:
        return self._is_calibrated
