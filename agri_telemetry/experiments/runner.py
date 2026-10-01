"""
Phase 2 Experiment Orchestrator and Benchmarking Engine.
Executes the controlled forecast ablation ladder on the protected chronological test split.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from agri_telemetry.domain.enums import VariableName
from agri_telemetry.ingestion import parse_uscrn_file, normalize_uscrn_dataframe
from agri_telemetry.qc import Tier1QCEngine
from agri_telemetry.state import SoilProfileConfig, StateBuilder
from agri_telemetry.forecasting.persistence import PersistenceModel
from agri_telemetry.forecasting.baselines import ClimatologicalMeanModel, EWMAModel
from agri_telemetry.forecasting.statistical_ar import AutoregressiveForecaster
from agri_telemetry.forecasting.exogenous_model import EnvironmentalForecaster
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator


@dataclass
class ModelHorizonMetrics:
    model_name: str
    target_name: str
    horizon_hours: int
    sample_count: int
    mae: float
    rmse: float
    mbe: float
    mse: float
    skill_vs_persistence: float
    skill_vs_climatology: float
    coverage_80: float
    interval_width_80: float


@dataclass
class ExperimentResult:
    experiment_id: str
    description: str
    target_variable: str
    test_start: datetime
    test_end: datetime
    total_test_samples: int
    model_metrics: Dict[str, Dict[int, ModelHorizonMetrics]] = field(default_factory=dict)


class Phase2ExperimentRunner:
    """
    Executes Phase 2 forecasting benchmark experiments with strict temporal discipline.
    """

    def __init__(
        self,
        data_file: Optional[Path] = None,
        horizons: Optional[List[int]] = None,
        train_fraction: float = 0.50,
    ):
        self.data_file = data_file or (
            Path(__file__).parent.parent.parent / "data" / "uscrn" / "CRNH0203-2023-NE_Lincoln_11_SW.txt"
        )
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.train_fraction = train_fraction

        # Load raw data and build states
        self.raw_df = parse_uscrn_file(self.data_file)
        self.events = normalize_uscrn_dataframe(self.raw_df, "USCRN_NE_Lincoln_11_SW", "FIELD_LINCOLN_01")
        
        # QC filtering
        qc_engine = Tier1QCEngine()
        self.valid_events = []
        for e in self.events:
            ev, is_q, _ = qc_engine.evaluate_event(e)
            if not is_q:
                self.valid_events.append(ev)

        # State building
        builder = StateBuilder(SoilProfileConfig())
        self.states = [builder.build_state(e) for e in self.valid_events]
        self.states = [s for s in self.states if s and s.is_valid]

        self.timestamps = [s.timestamp for s in self.states]
        self.theta_rz_series = [s.theta_rz for s in self.states]
        self.depletion_series = [s.depletion_fraction for s in self.states]
        
        # Extract 10cm topsoil VWC directly matching states
        self.theta_10cm_series = [s.depth_vwc.get(10.0, s.theta_rz) for s in self.states]

        # Align meteorological features strictly with valid state timestamps
        raw_indexed = self.raw_df.drop_duplicates(subset=["timestamp_utc"]).set_index("timestamp_utc")
        self.aligned_met_df = raw_indexed.reindex(self.timestamps).reset_index()

        # Split index (50/50 chronological)
        self.split_idx = int(len(self.states) * self.train_fraction)
        self.test_timestamps = self.timestamps[self.split_idx:]

    def run_all_experiments(self) -> Dict[str, ExperimentResult]:
        """
        Runs the complete Phase 2 ablation matrix.
        """
        results: Dict[str, ExperimentResult] = {}

        print("--> Running Experiment F2-01 to F2-03 (Baseline Ladder & Statistical Models on Root-Zone VWC)...")
        res_f2_01 = self.evaluate_models_on_series(
            series=self.theta_rz_series,
            target_name="root_zone_vwc",
            experiment_id="F2-01_to_F2-03",
            description="Comparison of Persistence, Climatological Mean, EWMA, Autoregressive (AR), and Environmental ARX on theta_rz",
        )
        results["F2-01_main"] = res_f2_01

        print("--> Running Experiment F2-04 (State Target Comparison: Topsoil 10cm VWC)...")
        res_10cm = self.evaluate_models_on_series(
            series=self.theta_10cm_series,
            target_name="topsoil_10cm_vwc",
            experiment_id="F2-04_10cm",
            description="Persistence vs ARX on topsoil 10cm VWC",
        )
        results["F2-04_10cm"] = res_10cm

        print("--> Running Experiment F2-04 (State Target Comparison: Root-Zone Depletion Fraction Dr)...")
        res_depletion = self.evaluate_models_on_series(
            series=self.depletion_series,
            target_name="root_zone_depletion_fraction",
            experiment_id="F2-04_depletion",
            description="Persistence vs ARX on root-zone depletion fraction Dr",
            min_bound=-0.5,
            max_bound=1.5,
        )
        results["F2-04_depletion"] = res_depletion

        return results

    def evaluate_models_on_series(
        self,
        series: List[float],
        target_name: str,
        experiment_id: str,
        description: str,
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> ExperimentResult:
        """
        Chronologically trains on H1 and evaluates on untouched H2 test split.
        """
        train_series = series[: self.split_idx]
        train_timestamps = self.timestamps[: self.split_idx]
        test_series = series[self.split_idx :]
        test_timestamps = self.timestamps[self.split_idx :]

        train_met_df = self.aligned_met_df.iloc[: self.split_idx].copy()
        test_met_df = self.aligned_met_df.iloc[self.split_idx :].copy()

        # 1. Fit Persistence Calibrator
        cal_persist = EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        cal_persist.fit(train_series)
        model_persist = PersistenceModel(horizons=self.horizons, calibrator=cal_persist)

        # 2. Climatology Mean Model
        model_clim = ClimatologicalMeanModel(horizons=self.horizons, calibrator=cal_persist)

        # 3. EWMA Model (alpha=0.15 calibrated on H1)
        model_ewma = EWMAModel(alpha=0.15, horizons=self.horizons, calibrator=cal_persist)

        # 4. Statistical AR Model
        model_ar = AutoregressiveForecaster(horizons=self.horizons, ridge_alpha=1.0)
        model_ar.fit(train_timestamps, train_series)

        # 5. Environmental Exogenous Forecaster
        model_env = EnvironmentalForecaster(horizons=self.horizons, ridge_alpha=10.0)
        model_env.fit(train_timestamps, train_series, met_df=train_met_df)

        n_test = len(test_series)
        train_clean = [v for v in train_series if v is not None and not np.isnan(v)]
        train_mean = float(np.mean(train_clean)) if train_clean else 0.25

        # Precompute feature matrices for test set in a single pass
        X_test_ar, _ = model_ar.extractor.extract_features(test_timestamps, test_series)
        X_test_env, _ = model_env.extractor.extract_features(test_timestamps, test_series, met_df=test_met_df)

        # Precompute EWMA levels across test set
        ewma_levels = np.zeros(n_test, dtype=float)
        s_prev = train_clean[-1] if train_clean else 0.25
        for i in range(n_test):
            s_prev = 0.15 * test_series[i] + 0.85 * s_prev
            ewma_levels[i] = s_prev

        # Precompute baseline reference MSEs for persistence and climatology
        persistence_mses: Dict[int, float] = {}
        climatology_mses: Dict[int, float] = {}

        for h in self.horizons:
            errs_p = []
            errs_c = []
            for t in range(n_test - h):
                y_t = test_series[t]
                y_act = test_series[t + h]
                if y_t is None or y_act is None or np.isnan(y_t) or np.isnan(y_act):
                    continue
                errs_p.append((y_act - y_t) ** 2)
                errs_c.append((y_act - train_mean) ** 2)
            persistence_mses[h] = float(np.mean(errs_p)) if errs_p else 1e-6
            climatology_mses[h] = float(np.mean(errs_c)) if errs_c else 1e-6

        models_dict = {
            "B0_PERSISTENCE": model_persist,
            "B1_CLIMATOLOGY": model_clim,
            "B2_EWMA": model_ewma,
            "M1_AUTOREGRESSIVE": model_ar,
            "M2_ENVIRONMENTAL_ARX": model_env,
        }

        model_metrics: Dict[str, Dict[int, ModelHorizonMetrics]] = {}

        for m_name, model in models_dict.items():
            model_metrics[m_name] = {}

            for h in self.horizons:
                errors: List[float] = []
                coverages: List[int] = []
                widths: List[float] = []

                for t in range(n_test - h):
                    y_t = test_series[t]
                    y_actual = test_series[t + h]
                    if y_t is None or y_actual is None or np.isnan(y_t) or np.isnan(y_actual):
                        continue

                    cur_time = test_timestamps[t]

                    if m_name == "B0_PERSISTENCE":
                        preds = model.predict(y_t, cur_time, min_bound=min_bound, max_bound=max_bound)
                    elif m_name == "B1_CLIMATOLOGY":
                        # Constant mean forecast
                        preds = model.predict(train_series, cur_time, min_bound=min_bound, max_bound=max_bound)
                    elif m_name == "B2_EWMA":
                        # EWMA level forecast
                        point_ewma = float(np.clip(ewma_levels[t], min_bound, max_bound))
                        preds = model.predict([point_ewma], cur_time, min_bound=min_bound, max_bound=max_bound)
                    elif m_name == "M1_AUTOREGRESSIVE":
                        preds = model.predict_from_feature_vector(X_test_ar[t], cur_time, y_t, min_bound=min_bound, max_bound=max_bound)
                    else:  # M2_ENVIRONMENTAL_ARX
                        preds = model.predict_from_feature_vector(X_test_env[t], cur_time, y_t, min_bound=min_bound, max_bound=max_bound)

                    pred_h = next((p for p in preds if p.horizon_hours == h), None)
                    if not pred_h:
                        continue

                    err = y_actual - pred_h.point_forecast
                    errors.append(err)

                    if pred_h.pi_lower_80 is not None and pred_h.pi_upper_80 is not None:
                        is_covered = 1 if (pred_h.pi_lower_80 <= y_actual <= pred_h.pi_upper_80) else 0
                        coverages.append(is_covered)
                        widths.append(pred_h.pi_upper_80 - pred_h.pi_lower_80)

                if errors:
                    err_arr = np.array(errors)
                    mae = float(np.mean(np.abs(err_arr)))
                    mse = float(np.mean(err_arr ** 2))
                    rmse = float(np.sqrt(mse))
                    mbe = float(np.mean(err_arr))
                    cov = float(np.mean(coverages)) if coverages else 0.0
                    w_avg = float(np.mean(widths)) if widths else 0.0

                    p_mse = persistence_mses.get(h, 1e-6)
                    c_mse = climatology_mses.get(h, 1e-6)

                    skill_p = float(1.0 - (mse / p_mse)) if p_mse > 0 else 0.0
                    skill_c = float(1.0 - (mse / c_mse)) if c_mse > 0 else 0.0

                    model_metrics[m_name][h] = ModelHorizonMetrics(
                        model_name=m_name,
                        target_name=target_name,
                        horizon_hours=h,
                        sample_count=len(errors),
                        mae=mae,
                        rmse=rmse,
                        mbe=mbe,
                        mse=mse,
                        skill_vs_persistence=skill_p,
                        skill_vs_climatology=skill_c,
                        coverage_80=cov,
                        interval_width_80=w_avg,
                    )

        return ExperimentResult(
            experiment_id=experiment_id,
            description=description,
            target_variable=target_name,
            test_start=test_timestamps[0],
            test_end=test_timestamps[-1],
            total_test_samples=len(test_timestamps),
            model_metrics=model_metrics,
        )


def format_comparison_markdown_table(result: ExperimentResult, horizon_filter: Optional[List[int]] = None) -> str:
    """Formats Markdown ablation table comparing all models across horizons."""
    horizons = horizon_filter or [1, 6, 12, 24, 48, 72, 168]
    lines = [
        f"### Experiment `{result.experiment_id}`: {result.description}",
        f"- **Target Variable**: `{result.target_variable}`",
        f"- **Protected Test Window**: `{result.test_start.isoformat()}` to `{result.test_end.isoformat()}` ($N = {result.total_test_samples:,}$ hours)",
        "",
        "| Model | Horizon | MAE | RMSE | Bias (MBE) | Skill vs Persistence | 80% Coverage | 80% Width |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for m_name, h_dict in result.model_metrics.items():
        for h in horizons:
            if h not in h_dict:
                continue
            m = h_dict[h]
            skill_str = f"**{m.skill_vs_persistence:+.3f}**" if abs(m.skill_vs_persistence) > 0.001 else "0.000 (bench)"
            cov_str = f"{m.coverage_80 * 100:.1f}%"
            lines.append(
                f"| `{m_name}` | `{h}h` | {m.mae:.4f} | {m.rmse:.4f} | {m.mbe:+.4f} | {skill_str} | {cov_str} | {m.interval_width_80:.4f} |"
            )

    return "\n".join(lines)
