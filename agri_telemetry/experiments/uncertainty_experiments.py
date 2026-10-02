"""
Phase 3 Experiment Suite: Horizon Partitioning, Future Weather (NWP) Value, and Uncertainty Calibration.
Strictly preserves chronological separation (H1 Train -> Untouched H2 Test).
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from agri_telemetry.experiments.runner import Phase2ExperimentRunner, ExperimentResult, ModelHorizonMetrics
from agri_telemetry.forecasting.uncertainty_calibration import (
    StaticQuantileCalibrator,
    HorizonDispersionCalibrator,
    RegimeConditionedCalibrator,
    PowerLawDispersionCalibrator,
    UncertaintyEvaluationMetrics,
)
from agri_telemetry.forecasting.statistical_ar import AutoregressiveForecaster
from agri_telemetry.forecasting.exogenous_model import EnvironmentalForecaster
from agri_telemetry.forecasting.persistence import PersistenceModel
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator


@dataclass
class HorizonPartitionResult:
    target_name: str
    sample_size: int
    metrics_by_horizon: Dict[int, Dict[str, Any]]


@dataclass
class NWPValueResult:
    target_name: str
    sample_size: int
    metrics_by_horizon: Dict[int, Dict[str, Any]]


@dataclass
class UncertaintyBenchmarkResult:
    target_name: str
    sample_size: int
    methods: Dict[str, List[UncertaintyEvaluationMetrics]]


class Phase3ExperimentRunner:
    """
    Executes Phase 3 investigations:
    1. Horizon-Partitioned Forecasting Evaluation (M2 for 1-48h, M1 for 72-168h)
    2. Future Weather (NWP) Value Investigation (Oracle precipitation ablation)
    3. Uncertainty Calibration & Dispersion Scaling across environmental regimes
    """

    def __init__(self, runner: Optional[Phase2ExperimentRunner] = None):
        self.runner = runner or Phase2ExperimentRunner()
        self.split_idx = self.runner.split_idx
        self.horizons = self.runner.horizons

        self.train_timestamps = self.runner.timestamps[: self.split_idx]
        self.test_timestamps = self.runner.timestamps[self.split_idx :]

        self.train_rz = self.runner.theta_rz_series[: self.split_idx]
        self.test_rz = self.runner.theta_rz_series[self.split_idx :]

        self.train_10cm = self.runner.theta_10cm_series[: self.split_idx]
        self.test_10cm = self.runner.theta_10cm_series[self.split_idx :]

        self.train_depletion = self.runner.depletion_series[: self.split_idx]
        self.test_depletion = self.runner.depletion_series[self.split_idx :]

        self.train_met = self.runner.aligned_met_df.iloc[: self.split_idx].copy()
        self.test_met = self.runner.aligned_met_df.iloc[self.split_idx :].copy()

    def run_horizon_partitioned_evaluation(self) -> HorizonPartitionResult:
        """
        Evaluates the Horizon-Partitioned Hybrid Forecaster:
        - h in [1, 6, 12, 24, 48]: Environmental Forecaster (M2)
        - h in [72, 168]: Autoregressive Forecaster (M1)
        Compared against Persistence (B0).
        """
        # Fit persistence calibrator and baseline
        cal_persist = EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        cal_persist.fit(self.train_rz)
        model_persist = PersistenceModel(horizons=self.horizons, calibrator=cal_persist)

        # Fit M1 (AR)
        model_ar = AutoregressiveForecaster(horizons=self.horizons, ridge_alpha=1.0)
        model_ar.fit(self.train_timestamps, self.train_rz)

        # Fit M2 (Environmental ARX)
        model_env = EnvironmentalForecaster(horizons=self.horizons, ridge_alpha=10.0)
        model_env.fit(self.train_timestamps, self.train_rz, met_df=self.train_met)

        n_test = len(self.test_rz)
        X_test_ar, _ = model_ar.extractor.extract_features(self.test_timestamps, self.test_rz)
        X_test_env, _ = model_env.extractor.extract_features(self.test_timestamps, self.test_rz, met_df=self.test_met)

        metrics_by_h: Dict[int, Dict[str, Any]] = {}

        for h in self.horizons:
            if n_test <= h:
                continue

            y_true = np.array(self.test_rz[h:], dtype=float)
            valid_mask = ~np.isnan(y_true)

            # Persistence prediction
            y_persist = np.array(self.test_rz[:-h], dtype=float)

            # Select model based on partition
            if h <= 48:
                assigned_model = "M2_ENVIRONMENTAL_ARX"
                preds_full = model_env.predict_vectorized(X_test_env, horizon=h)
                y_pred = preds_full[:-h]
            else:
                assigned_model = "M1_AUTOREGRESSIVE"
                preds_full = model_ar.predict_vectorized(X_test_ar, horizon=h)
                y_pred = preds_full[:-h]

            # Compute errors on valid steps
            y_t = y_true[valid_mask]
            y_p = y_pred[valid_mask]
            y_b = y_persist[valid_mask]

            mae_model = float(np.mean(np.abs(y_p - y_t)))
            rmse_model = float(np.sqrt(np.mean((y_p - y_t) ** 2)))
            mbe_model = float(np.mean(y_p - y_t))

            mae_bench = float(np.mean(np.abs(y_b - y_t)))
            rmse_bench = float(np.sqrt(np.mean((y_b - y_t) ** 2)))
            mbe_bench = float(np.mean(y_b - y_t))

            mse_model = float(np.mean((y_p - y_t) ** 2))
            mse_bench = float(np.mean((y_b - y_t) ** 2))
            skill = 1.0 - (mse_model / max(mse_bench, 1e-12))

            metrics_by_h[h] = {
                "assigned_model": assigned_model,
                "mae_hybrid": mae_model,
                "rmse_hybrid": rmse_model,
                "mbe_hybrid": mbe_model,
                "mae_persist": mae_bench,
                "rmse_persist": rmse_bench,
                "skill_vs_persist": skill,
                "n_eval": int(np.sum(valid_mask)),
            }

        return HorizonPartitionResult(
            target_name="root_zone_vwc",
            sample_size=n_test,
            metrics_by_horizon=metrics_by_h,
        )

    def run_future_weather_nwp_investigation(self) -> NWPValueResult:
        """
        Investigates the value of future weather information (NWP oracle ablation).
        Compares:
        1. Persistence (B0)
        2. Standard M2 ARX (past precipitation accumulation only)
        3. Oracle NWP ARX (given exact future cumulative precipitation over horizon h)
        """
        n_test = len(self.test_rz)
        n_train = len(self.train_rz)

        # Build feature matrix including future precip oracle for training and test
        # Train oracle
        train_p = self.train_met["precip_mm"].fillna(0.0).values
        test_p = self.test_met["precip_mm"].fillna(0.0).values

        metrics_by_h: Dict[int, Dict[str, Any]] = {}

        for h in self.horizons:
            if n_test <= h:
                continue

            # Standard M2 predictions
            model_env = EnvironmentalForecaster(horizons=[h], ridge_alpha=10.0)
            model_env.fit(self.train_timestamps, self.train_rz, met_df=self.train_met)

            X_test_env, _ = model_env.extractor.extract_features(self.test_timestamps, self.test_rz, met_df=self.test_met)
            preds_m2 = model_env.predict_vectorized(X_test_env, horizon=h)[:-h]

            # Build Oracle NWP Model (adds future precip sum from t to t+h)
            # Train features with future sum
            X_tr, _ = model_env.extractor.extract_features(self.train_timestamps, self.train_rz, met_df=self.train_met)
            # Add future precip column
            future_p_train = np.zeros(n_train, dtype=float)
            for i in range(n_train - h):
                future_p_train[i] = np.sum(train_p[i : i + h])

            X_tr_oracle = np.column_stack([X_tr, future_p_train])

            y_tr_target = np.array(self.train_rz, dtype=float)
            valid_tr = ~np.isnan(y_tr_target[h:])
            X_fit = X_tr_oracle[:-h][valid_tr]
            mean_fit = np.mean(X_fit, axis=0)
            std_fit = np.std(X_fit, axis=0)
            std_fit[std_fit == 0.0] = 1.0

            X_fit_norm = (X_fit - mean_fit) / std_fit
            y_fit = y_tr_target[h:][valid_tr]
            from sklearn.linear_model import Ridge
            oracle_ridge = Ridge(alpha=10.0)
            oracle_ridge.fit(X_fit_norm, y_fit)

            # Test features with future sum
            future_p_test = np.zeros(n_test, dtype=float)
            for i in range(n_test - h):
                future_p_test[i] = np.sum(test_p[i : i + h])

            X_te_oracle = np.column_stack([X_test_env, future_p_test])
            X_te_norm = (X_te_oracle[:-h] - mean_fit) / std_fit
            preds_oracle = np.clip(oracle_ridge.predict(X_te_norm), 0.0, 0.60)

            # True test targets
            y_true = np.array(self.test_rz[h:], dtype=float)
            y_persist = np.array(self.test_rz[:-h], dtype=float)
            valid = ~np.isnan(y_true)

            y_t = y_true[valid]
            y_p_m2 = preds_m2[valid]
            y_p_ora = preds_oracle[valid]
            y_p_b = y_persist[valid]

            mse_b = float(np.mean((y_p_b - y_t) ** 2))
            mse_m2 = float(np.mean((y_p_m2 - y_t) ** 2))
            mse_ora = float(np.mean((y_p_ora - y_t) ** 2))

            skill_m2 = 1.0 - (mse_m2 / max(mse_b, 1e-12))
            skill_ora = 1.0 - (mse_ora / max(mse_b, 1e-12))

            metrics_by_h[h] = {
                "rmse_persist": float(np.sqrt(mse_b)),
                "rmse_past_arx": float(np.sqrt(mse_m2)),
                "skill_past_arx": skill_m2,
                "rmse_nwp_oracle": float(np.sqrt(mse_ora)),
                "skill_nwp_oracle": skill_ora,
                "n_eval": int(np.sum(valid)),
            }

        return NWPValueResult(
            target_name="root_zone_vwc",
            sample_size=n_test,
            metrics_by_horizon=metrics_by_h,
        )

    def run_uncertainty_benchmark(self, nominal_coverages: Optional[List[float]] = None) -> UncertaintyBenchmarkResult:
        """
        Compares U0 (Static Quantiles), U1 (Horizon Dispersion), U2 (Regime-Conditioned), U3 (Power-Law).
        Evaluates empirical coverage, width, and regime-partitioned performance on untouched H2.
        """
        nom_list = nominal_coverages or [0.80, 0.90]

        # 1. Fit all calibrators strictly on H1
        u0 = StaticQuantileCalibrator(horizons=self.horizons).fit(self.train_rz)
        u1 = HorizonDispersionCalibrator(horizons=self.horizons, use_mad=True).fit(self.train_rz)
        u2 = RegimeConditionedCalibrator(horizons=self.horizons).fit(self.train_rz, met_df=self.train_met)
        u3 = PowerLawDispersionCalibrator(horizons=self.horizons).fit(self.train_rz)

        n_test = len(self.test_rz)
        test_p24 = pd.Series(self.test_met["precip_mm"].fillna(0.0)).rolling(24, min_periods=1).sum().values
        test_solar = self.test_met["solar_rad_wm2"].fillna(0.0).values

        # Tag test regimes
        test_regimes = [
            RegimeConditionedCalibrator.classify_regime(test_p24[i], test_solar[i])
            for i in range(n_test)
        ]

        methods_dict: Dict[str, List[UncertaintyEvaluationMetrics]] = {
            "U0_STATIC_QUANTILES": [],
            "U1_HORIZON_DISPERSION_MAD": [],
            "U2_REGIME_CONDITIONED": [],
            "U3_POWER_LAW_DISPERSION": [],
        }

        for nom in nom_list:
            for h in self.horizons:
                if n_test <= h:
                    continue

                y_true = np.array(self.test_rz[h:], dtype=float)
                y_point = np.array(self.test_rz[:-h], dtype=float)
                valid = ~np.isnan(y_true)

                y_t = y_true[valid]
                y_pt = y_point[valid]
                h_regimes = np.array(test_regimes[:-h])[valid]
                n_eval = len(y_t)

                # Evaluate U0
                u0_int = [u0.predict_interval(pt, h, nominal_coverage=nom) for pt in y_pt]
                cov_u0 = float(np.mean([1.0 if ip.lower_bound <= yt <= ip.upper_bound else 0.0 for ip, yt in zip(u0_int, y_t)]))
                w_u0 = float(np.mean([ip.interval_width for ip in u0_int]))
                reg_u0 = self._compute_regime_breakdown(u0_int, y_t, h_regimes)
                methods_dict["U0_STATIC_QUANTILES"].append(
                    UncertaintyEvaluationMetrics("U0_STATIC_QUANTILES", h, nom, cov_u0, w_u0, n_eval, reg_u0)
                )

                # Evaluate U1
                u1_int = [u1.predict_interval(pt, h, nominal_coverage=nom) for pt in y_pt]
                cov_u1 = float(np.mean([1.0 if ip.lower_bound <= yt <= ip.upper_bound else 0.0 for ip, yt in zip(u1_int, y_t)]))
                w_u1 = float(np.mean([ip.interval_width for ip in u1_int]))
                reg_u1 = self._compute_regime_breakdown(u1_int, y_t, h_regimes)
                methods_dict["U1_HORIZON_DISPERSION_MAD"].append(
                    UncertaintyEvaluationMetrics("U1_HORIZON_DISPERSION_MAD", h, nom, cov_u1, w_u1, n_eval, reg_u1)
                )

                # Evaluate U2
                u2_int = [
                    u2.predict_interval(
                        pt,
                        h,
                        precip_24h=test_p24[i],
                        solar_rad=test_solar[i],
                        nominal_coverage=nom,
                    )
                    for i, pt in enumerate(y_pt)
                ]
                cov_u2 = float(np.mean([1.0 if ip.lower_bound <= yt <= ip.upper_bound else 0.0 for ip, yt in zip(u2_int, y_t)]))
                w_u2 = float(np.mean([ip.interval_width for ip in u2_int]))
                reg_u2 = self._compute_regime_breakdown(u2_int, y_t, h_regimes)
                methods_dict["U2_REGIME_CONDITIONED"].append(
                    UncertaintyEvaluationMetrics("U2_REGIME_CONDITIONED", h, nom, cov_u2, w_u2, n_eval, reg_u2)
                )

                # Evaluate U3
                u3_int = [u3.predict_interval(pt, h, nominal_coverage=nom) for pt in y_pt]
                cov_u3 = float(np.mean([1.0 if ip.lower_bound <= yt <= ip.upper_bound else 0.0 for ip, yt in zip(u3_int, y_t)]))
                w_u3 = float(np.mean([ip.interval_width for ip in u3_int]))
                reg_u3 = self._compute_regime_breakdown(u3_int, y_t, h_regimes)
                methods_dict["U3_POWER_LAW_DISPERSION"].append(
                    UncertaintyEvaluationMetrics("U3_POWER_LAW_DISPERSION", h, nom, cov_u3, w_u3, n_eval, reg_u3)
                )

        return UncertaintyBenchmarkResult(
            target_name="root_zone_vwc",
            sample_size=n_test,
            methods=methods_dict,
        )

    @staticmethod
    def _compute_regime_breakdown(
        intervals: List[Any],
        y_true: np.ndarray,
        regimes: np.ndarray,
    ) -> Dict[str, Dict[str, float]]:
        out = {}
        unique_regs = np.unique(regimes)
        for r in unique_regs:
            mask = regimes == r
            if np.sum(mask) == 0:
                continue
            r_int = [intervals[i] for i in range(len(intervals)) if mask[i]]
            r_yt = y_true[mask]
            cov = float(np.mean([1.0 if ip.lower_bound <= yt <= ip.upper_bound else 0.0 for ip, yt in zip(r_int, r_yt)]))
            w = float(np.mean([ip.interval_width for ip in r_int]))
            out[str(r)] = {
                "coverage": cov,
                "mean_width": w,
                "n_samples": int(np.sum(mask)),
            }
        return out
