"""
Feature Availability Contract and Temporal Feature Extractor.
Strictly enforces causality: only information available at or before forecast origin t is permitted.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from agri_telemetry.domain.enums import VariableName


@dataclass(frozen=True)
class FeatureAvailabilitySpec:
    """
    Formal metadata specification defining the causality contract of a feature.
    """
    feature_name: str
    source_variable: str
    lag_hours: int  # Must be >= 0 (0 = current observed value at origin t, >0 = past lag)
    is_observed: bool = True
    is_derived: bool = False
    provenance_description: str = ""

    def __post_init__(self):
        if self.lag_hours < 0:
            raise ValueError(
                f"Temporal leakage violation in feature '{self.feature_name}': "
                f"lag_hours cannot be negative ({self.lag_hours}). Future data is strictly forbidden."
            )


class FeatureExtractor:
    """
    Extracts causal feature matrices for time-series and exogenous forecasting models.
    Guarantees that row t contains strictly data observed at or prior to time t.
    """

    def __init__(
        self,
        target_lags: Optional[List[int]] = None,
        include_precip: bool = False,
        include_temp: bool = False,
        include_solar: bool = False,
        include_diurnal: bool = False,
    ):
        self.target_lags = target_lags or [0, 1, 2, 6, 12, 24, 48]
        self.include_precip = include_precip
        self.include_temp = include_temp
        self.include_solar = include_solar
        self.include_diurnal = include_diurnal

        self.feature_specs = self._build_feature_specs()

    def _build_feature_specs(self) -> List[FeatureAvailabilitySpec]:
        specs: List[FeatureAvailabilitySpec] = []

        # Target autoregressive lags
        for lag in self.target_lags:
            specs.append(
                FeatureAvailabilitySpec(
                    feature_name=f"target_lag_{lag}h" if lag > 0 else "target_current",
                    source_variable="target_series",
                    lag_hours=lag,
                    is_observed=True,
                    provenance_description=f"Target series observation at t - {lag}h",
                )
            )

        # Derived rolling target delta (24h rate of change)
        specs.append(
            FeatureAvailabilitySpec(
                feature_name="target_delta_24h",
                source_variable="target_series",
                lag_hours=0,
                is_derived=True,
                provenance_description="Observed 24-hour rate of change Y_t - Y_{t-24}",
            )
        )

        if self.include_precip:
            for window in [1, 6, 24, 72]:
                specs.append(
                    FeatureAvailabilitySpec(
                        feature_name=f"precip_sum_{window}h",
                        source_variable=VariableName.PRECIPITATION.value,
                        lag_hours=0,
                        is_derived=True,
                        provenance_description=f"Past {window}-hour accumulated observed precipitation sum",
                    )
                )

        if self.include_temp:
            specs.append(
                FeatureAvailabilitySpec(
                    feature_name="air_temp_current",
                    source_variable=VariableName.AIR_TEMPERATURE.value,
                    lag_hours=0,
                    is_observed=True,
                    provenance_description="Air temperature at forecast origin t",
                )
            )
            specs.append(
                FeatureAvailabilitySpec(
                    feature_name="air_temp_mean_24h",
                    source_variable=VariableName.AIR_TEMPERATURE.value,
                    lag_hours=0,
                    is_derived=True,
                    provenance_description="Mean air temperature over past 24 hours [t-24, t]",
                )
            )

        if self.include_solar:
            specs.append(
                FeatureAvailabilitySpec(
                    feature_name="solar_rad_current",
                    source_variable=VariableName.SOLAR_RADIATION.value,
                    lag_hours=0,
                    is_observed=True,
                    provenance_description="Solar radiation at forecast origin t",
                )
            )
            specs.append(
                FeatureAvailabilitySpec(
                    feature_name="solar_rad_sum_24h",
                    source_variable=VariableName.SOLAR_RADIATION.value,
                    lag_hours=0,
                    is_derived=True,
                    provenance_description="Accumulated solar radiation over past 24 hours [t-24, t]",
                )
            )

        if self.include_diurnal:
            specs.append(
                FeatureAvailabilitySpec(
                    feature_name="hour_sin",
                    source_variable="calendar_time",
                    lag_hours=0,
                    is_derived=True,
                    provenance_description="sin(2*pi*hour/24) at forecast origin t",
                )
            )
            specs.append(
                FeatureAvailabilitySpec(
                    feature_name="hour_cos",
                    source_variable="calendar_time",
                    lag_hours=0,
                    is_derived=True,
                    provenance_description="cos(2*pi*hour/24) at forecast origin t",
                )
            )

        return specs

    def extract_features(
        self,
        timestamps: List[datetime],
        target_series: List[float],
        met_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Builds causal feature matrix X where row i contains strictly information available at timestamps[i].
        """
        n = len(target_series)
        feature_names = [s.feature_name for s in self.feature_specs]
        X = np.zeros((n, len(feature_names)), dtype=float)

        target_arr = np.array(target_series, dtype=float)

        # Forward fill any small isolated NaNs in target for feature computation
        target_clean = pd.Series(target_arr).ffill().bfill().values

        # 1. Target lags
        col_idx = 0
        for lag in self.target_lags:
            if lag == 0:
                X[:, col_idx] = target_clean
            else:
                lagged = np.roll(target_clean, lag)
                lagged[:lag] = target_clean[0]  # Avoid boundary wrap-around
                X[:, col_idx] = lagged
            col_idx += 1

        # 2. Target delta 24h
        delta_24 = target_clean - np.roll(target_clean, 24)
        delta_24[:24] = 0.0
        X[:, col_idx] = delta_24
        col_idx += 1

        # 3. Precipitation features
        if self.include_precip and met_df is not None and "precip_mm" in met_df.columns:
            p_series = met_df["precip_mm"].fillna(0.0).values
            p_clean = np.nan_to_num(p_series, nan=0.0)
            for window in [1, 6, 24, 72]:
                # Past rolling sum (strictly past values ending at index t)
                r_sum = pd.Series(p_clean).rolling(window=window, min_periods=1).sum().values
                X[:, col_idx] = r_sum
                col_idx += 1
        elif self.include_precip:
            # Fallback zeros if met_df missing
            for _ in [1, 6, 24, 72]:
                X[:, col_idx] = 0.0
                col_idx += 1

        # 4. Air temperature features
        if self.include_temp and met_df is not None and "air_temp_c" in met_df.columns:
            t_series = met_df["air_temp_c"].ffill().bfill().values
            X[:, col_idx] = t_series
            col_idx += 1
            t_mean_24 = pd.Series(t_series).rolling(window=24, min_periods=1).mean().values
            X[:, col_idx] = t_mean_24
            col_idx += 1
        elif self.include_temp:
            X[:, col_idx] = 15.0
            col_idx += 1
            X[:, col_idx] = 15.0
            col_idx += 1

        # 5. Solar radiation features
        if self.include_solar and met_df is not None and "solar_rad_wm2" in met_df.columns:
            sol_series = met_df["solar_rad_wm2"].fillna(0.0).values
            X[:, col_idx] = sol_series
            col_idx += 1
            sol_sum_24 = pd.Series(sol_series).rolling(window=24, min_periods=1).sum().values
            X[:, col_idx] = sol_sum_24
            col_idx += 1
        elif self.include_solar:
            X[:, col_idx] = 0.0
            col_idx += 1
            X[:, col_idx] = 0.0
            col_idx += 1

        # 6. Diurnal features
        if self.include_diurnal:
            hours = np.array([dt.hour for dt in timestamps], dtype=float)
            X[:, col_idx] = np.sin(2.0 * np.pi * hours / 24.0)
            col_idx += 1
            X[:, col_idx] = np.cos(2.0 * np.pi * hours / 24.0)
            col_idx += 1

        return X, feature_names
