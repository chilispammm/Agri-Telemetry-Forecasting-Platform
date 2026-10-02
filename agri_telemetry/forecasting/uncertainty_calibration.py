"""
Uncertainty Calibration & Dispersion Scaling Module.
Implements interpretable, leak-free uncertainty estimation methods:
- U0: Static Horizon Empirical Quantiles (Phase 1 Baseline)
- U1: Horizon-Specific Robust Dispersion Scaling (MAD / Std)
- U2: Environmental Condition-Scaled / Regime-Conditioned Dispersion (Antecedent Rain & Solar Demand)
- U3: Power-Law Horizon Variance Expansion (Physical sub-diffusive dispersion)

All calibrators are strictly fitted on historical walk-forward residuals (H1) and evaluated out-of-sample (H2).
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd


@dataclass
class IntervalPrediction:
    horizon_hours: int
    point_forecast: float
    nominal_coverage: float
    lower_bound: float
    upper_bound: float
    interval_width: float
    regime_tag: Optional[str] = None


@dataclass
class UncertaintyEvaluationMetrics:
    method_name: str
    horizon_hours: int
    nominal_coverage: float
    empirical_coverage: float  # PICP
    mean_interval_width: float
    sample_size: int
    regime_breakdown: Dict[str, Dict[str, float]]  # {regime: {"coverage": float, "width": float, "n": int}}


class StaticQuantileCalibrator:
    """
    Method U0: Static empirical quantiles of walk-forward residuals per horizon.
    [q_{alpha/2}, q_{1-alpha/2}]
    """

    def __init__(self, horizons: Optional[List[int]] = None):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self._residuals: Dict[int, np.ndarray] = {}
        self._is_fitted = False

    def fit(self, train_series: List[float]) -> "StaticQuantileCalibrator":
        arr = np.array(train_series, dtype=float)
        n = len(arr)
        self._residuals.clear()

        for h in self.horizons:
            if n > h:
                errs = arr[h:] - arr[:-h]
                valid_mask = ~np.isnan(errs)
                self._residuals[h] = errs[valid_mask]
            else:
                self._residuals[h] = np.array([0.0])

        self._is_fitted = True
        return self

    def predict_interval(
        self,
        point_forecast: float,
        horizon_hours: int,
        nominal_coverage: float = 0.80,
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> IntervalPrediction:
        errs = self._residuals.get(horizon_hours, np.array([0.0]))
        if len(errs) == 0:
            errs = np.array([0.0])

        alpha = 1.0 - nominal_coverage
        lower_pct = 100.0 * (alpha / 2.0)
        upper_pct = 100.0 * (1.0 - alpha / 2.0)

        delta_lower = float(np.percentile(errs, lower_pct))
        delta_upper = float(np.percentile(errs, upper_pct))

        lb = float(np.clip(point_forecast + delta_lower, min_bound, max_bound))
        ub = float(np.clip(point_forecast + delta_upper, min_bound, max_bound))

        return IntervalPrediction(
            horizon_hours=horizon_hours,
            point_forecast=point_forecast,
            nominal_coverage=nominal_coverage,
            lower_bound=lb,
            upper_bound=ub,
            interval_width=max(0.0, ub - lb),
        )


class HorizonDispersionCalibrator:
    """
    Method U1: Horizon-specific robust dispersion scaling.
    Uses Median Absolute Deviation (MAD) or Standard Deviation per horizon:
    sigma_h = 1.4826 * median(|e_h - median(e_h)|)
    Interval: [point - z * sigma_h, point + z * sigma_h]
    """

    def __init__(self, horizons: Optional[List[int]] = None, use_mad: bool = True):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.use_mad = use_mad
        self.scale_per_horizon: Dict[int, float] = {}
        self.bias_per_horizon: Dict[int, float] = {}
        self._is_fitted = False

    def fit(self, train_series: List[float]) -> "HorizonDispersionCalibrator":
        arr = np.array(train_series, dtype=float)
        n = len(arr)

        for h in self.horizons:
            if n > h:
                errs = arr[h:] - arr[:-h]
                valid = errs[~np.isnan(errs)]
                if len(valid) > 0:
                    med = float(np.median(valid))
                    self.bias_per_horizon[h] = med
                    if self.use_mad:
                        mad = float(np.median(np.abs(valid - med)))
                        self.scale_per_horizon[h] = max(1e-5, 1.4826 * mad)
                    else:
                        self.scale_per_horizon[h] = max(1e-5, float(np.std(valid)))
                else:
                    self.bias_per_horizon[h] = 0.0
                    self.scale_per_horizon[h] = 0.01
            else:
                self.bias_per_horizon[h] = 0.0
                self.scale_per_horizon[h] = 0.01

        self._is_fitted = True
        return self

    def predict_interval(
        self,
        point_forecast: float,
        horizon_hours: int,
        nominal_coverage: float = 0.80,
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> IntervalPrediction:
        sigma = self.scale_per_horizon.get(horizon_hours, 0.01)
        bias = self.bias_per_horizon.get(horizon_hours, 0.0)

        # Normal critical values
        if nominal_coverage == 0.80:
            z = 1.28155
        elif nominal_coverage == 0.90:
            z = 1.64485
        elif nominal_coverage == 0.95:
            z = 1.95996
        else:
            from scipy.stats import norm
            z = float(norm.ppf(1.0 - (1.0 - nominal_coverage) / 2.0))

        center = point_forecast + bias
        lb = float(np.clip(center - z * sigma, min_bound, max_bound))
        ub = float(np.clip(center + z * sigma, min_bound, max_bound))

        return IntervalPrediction(
            horizon_hours=horizon_hours,
            point_forecast=point_forecast,
            nominal_coverage=nominal_coverage,
            lower_bound=lb,
            upper_bound=ub,
            interval_width=max(0.0, ub - lb),
        )


class RegimeConditionedCalibrator:
    """
    Method U2: Environmental Condition-Scaled / Regime-Conditioned Dispersion.
    Partitions H1 residuals by antecedent weather regime observed at forecast origin t:
    - Regime 'WET_ANTECEDENT': Past 24h precipitation > 1.0 mm (active infiltration / high variance)
    - Regime 'HIGH_EVAP': Past 24h precip <= 1.0 mm AND solar radiation >= 200 W/m2 (active daytime drying)
    - Regime 'DRY_QUIESCENT': Past 24h precip <= 1.0 mm AND solar radiation < 200 W/m2 (slow baseline capillary drydown)
    """

    def __init__(self, horizons: Optional[List[int]] = None):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        # {horizon: {regime: np.ndarray of residuals}}
        self._regime_residuals: Dict[int, Dict[str, np.ndarray]] = {h: {} for h in self.horizons}
        # Fallback global residuals
        self._global_residuals: Dict[int, np.ndarray] = {h: np.array([]) for h in self.horizons}
        self._is_fitted = False

    @staticmethod
    def classify_regime(precip_24h: float, solar_rad: float) -> str:
        if precip_24h > 1.0:
            return "WET_ANTECEDENT"
        elif solar_rad >= 200.0:
            return "HIGH_EVAP"
        else:
            return "DRY_QUIESCENT"

    def fit(
        self,
        train_series: List[float],
        met_df: pd.DataFrame,
    ) -> "RegimeConditionedCalibrator":
        arr = np.array(train_series, dtype=float)
        n = len(arr)

        p_series = met_df["precip_mm"].fillna(0.0).values
        p24_arr = pd.Series(p_series).rolling(24, min_periods=1).sum().values
        solar_arr = met_df["solar_rad_wm2"].fillna(0.0).values

        regimes = [
            self.classify_regime(p24_arr[i], solar_arr[i])
            for i in range(n)
        ]

        for h in self.horizons:
            self._regime_residuals[h] = {
                "WET_ANTECEDENT": [],
                "HIGH_EVAP": [],
                "DRY_QUIESCENT": [],
            }
            if n > h:
                errs = arr[h:] - arr[:-h]
                origin_regimes = regimes[:-h]
                valid = ~np.isnan(errs)

                self._global_residuals[h] = errs[valid]

                for err_val, reg, is_v in zip(errs, origin_regimes, valid):
                    if is_v:
                        self._regime_residuals[h][reg].append(err_val)

            for reg in ["WET_ANTECEDENT", "HIGH_EVAP", "DRY_QUIESCENT"]:
                lst = self._regime_residuals[h][reg]
                self._regime_residuals[h][reg] = np.array(lst) if len(lst) > 0 else self._global_residuals[h]

        self._is_fitted = True
        return self

    def predict_interval(
        self,
        point_forecast: float,
        horizon_hours: int,
        precip_24h: float,
        solar_rad: float,
        nominal_coverage: float = 0.80,
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> IntervalPrediction:
        regime = self.classify_regime(precip_24h, solar_rad)
        reg_errs = self._regime_residuals.get(horizon_hours, {}).get(regime, np.array([]))

        # Fallback to global if regime has too few samples
        if len(reg_errs) < 20:
            reg_errs = self._global_residuals.get(horizon_hours, np.array([0.0]))
        if len(reg_errs) == 0:
            reg_errs = np.array([0.0])

        alpha = 1.0 - nominal_coverage
        lower_pct = 100.0 * (alpha / 2.0)
        upper_pct = 100.0 * (1.0 - alpha / 2.0)

        delta_lower = float(np.percentile(reg_errs, lower_pct))
        delta_upper = float(np.percentile(reg_errs, upper_pct))

        lb = float(np.clip(point_forecast + delta_lower, min_bound, max_bound))
        ub = float(np.clip(point_forecast + delta_upper, min_bound, max_bound))

        return IntervalPrediction(
            horizon_hours=horizon_hours,
            point_forecast=point_forecast,
            nominal_coverage=nominal_coverage,
            lower_bound=lb,
            upper_bound=ub,
            interval_width=max(0.0, ub - lb),
            regime_tag=regime,
        )


class PowerLawDispersionCalibrator:
    """
    Method U3: Power-Law Horizon Variance Expansion.
    sigma(h) = sigma_1 * h^nu
    Captures sub-diffusive physical dispersion of soil water uncertainty across horizons.
    """

    def __init__(self, horizons: Optional[List[int]] = None):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.sigma_1 = 0.0018
        self.nu = 0.45
        self._is_fitted = False

    def fit(self, train_series: List[float]) -> "PowerLawDispersionCalibrator":
        arr = np.array(train_series, dtype=float)
        n = len(arr)

        h_list = []
        std_list = []
        for h in self.horizons:
            if n > h:
                errs = arr[h:] - arr[:-h]
                valid = errs[~np.isnan(errs)]
                if len(valid) > 20:
                    h_list.append(h)
                    std_list.append(float(np.std(valid)))

        if len(h_list) >= 3:
            # Fit log(std) = log(sigma_1) + nu * log(h) via linear regression
            std_clean = np.array([max(s, 1e-5) for s in std_list])
            log_h = np.log(np.array(h_list))
            log_std = np.log(std_clean)
            p = np.polyfit(log_h, log_std, 1)
            self.nu = float(p[0])
            self.sigma_1 = float(np.exp(p[1]))

        self._is_fitted = True
        return self

    def predict_interval(
        self,
        point_forecast: float,
        horizon_hours: int,
        nominal_coverage: float = 0.80,
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> IntervalPrediction:
        sigma_h = self.sigma_1 * (horizon_hours ** self.nu)

        if nominal_coverage == 0.80:
            z = 1.28155
        elif nominal_coverage == 0.90:
            z = 1.64485
        elif nominal_coverage == 0.95:
            z = 1.95996
        else:
            from scipy.stats import norm
            z = float(norm.ppf(1.0 - (1.0 - nominal_coverage) / 2.0))

        lb = float(np.clip(point_forecast - z * sigma_h, min_bound, max_bound))
        ub = float(np.clip(point_forecast + z * sigma_h, min_bound, max_bound))

        return IntervalPrediction(
            horizon_hours=horizon_hours,
            point_forecast=point_forecast,
            nominal_coverage=nominal_coverage,
            lower_bound=lb,
            upper_bound=ub,
            interval_width=max(0.0, ub - lb),
        )
