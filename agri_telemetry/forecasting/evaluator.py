"""
Walk-Forward Out-of-Sample Forecast Evaluator.
Performs leak-free chronological rolling evaluation and computes verification metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator
from agri_telemetry.forecasting.persistence import PersistenceModel


@dataclass
class HorizonEvaluationMetrics:
    horizon_hours: int
    sample_count: int
    mae: float
    rmse: float
    mbe: float
    coverage_80: float
    skill_score_vs_mean: float


@dataclass
class ForecastVerificationReport:
    model_name: str
    target_variable: str
    evaluation_start: datetime
    evaluation_end: datetime
    horizon_metrics: Dict[int, HorizonEvaluationMetrics] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_markdown_table(self) -> str:
        lines = [
            f"### Out-of-Sample Verification: {self.model_name} (`{self.target_variable}`)",
            f"- **Evaluation Period**: `{self.evaluation_start.isoformat()}` to `{self.evaluation_end.isoformat()}`",
            "",
            "| Horizon (h) | Test Samples | MAE (m³/m³) | RMSE (m³/m³) | MBE (m³/m³) | 80% PI Coverage | Skill vs Mean |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for h, m in sorted(self.horizon_metrics.items()):
            cov_str = f"{m.coverage_80 * 100:.1f}%"
            skill_str = f"{m.skill_score_vs_mean:+.3f}"
            lines.append(
                f"| `{h}h` | {m.sample_count:,} | {m.mae:.4f} | {m.rmse:.4f} | {m.mbe:+.4f} | {cov_str} | {skill_str} |"
            )
        return "\n".join(lines)


class WalkForwardEvaluator:
    """
    Executes chronological rolling walk-forward backtest without future information leakage.
    """

    def __init__(
        self,
        horizons: Optional[List[int]] = None,
        train_fraction: float = 0.50,
    ):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.train_fraction = train_fraction

    def evaluate(
        self,
        timestamps: List[datetime],
        values: List[float],
        target_variable: str = "volumetric_water_content",
    ) -> ForecastVerificationReport:
        """
        Splits series chronologically into train (calibration) and test (out-of-sample evaluation).
        """
        n = len(values)
        if n < (max(self.horizons) + 50):
            raise ValueError(f"Time series too short for walk-forward evaluation: N={n}")

        split_idx = int(n * self.train_fraction)
        train_values = values[:split_idx]
        test_values = values[split_idx:]
        test_timestamps = timestamps[split_idx:]

        # Fit empirical uncertainty calibrator on train split ONLY
        calibrator = EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        calibrator.fit(train_values)

        # Climatological baseline mean from train split
        train_clean = [v for v in train_values if v is not None and not np.isnan(v)]
        clim_mean = float(np.mean(train_clean)) if train_clean else 0.0

        model = PersistenceModel(horizons=self.horizons, calibrator=calibrator)

        horizon_results: Dict[int, HorizonEvaluationMetrics] = {}

        for h in self.horizons:
            n_test = len(test_values)
            if n_test <= h:
                continue

            errors: List[float] = []
            clim_errors: List[float] = []
            coverage_hits: int = 0
            valid_samples: int = 0

            for t in range(n_test - h):
                y_t = test_values[t]
                y_actual = test_values[t + h]

                if y_t is None or y_actual is None or np.isnan(y_t) or np.isnan(y_actual):
                    continue

                preds = model.predict(current_value=y_t, origin_time=test_timestamps[t])
                pred_h = next((p for p in preds if p.horizon_hours == h), None)
                if not pred_h:
                    continue

                # Point error (actual - predicted)
                err = y_actual - pred_h.point_forecast
                errors.append(err)
                clim_errors.append(y_actual - clim_mean)
                valid_samples += 1

                # Check 80% prediction interval coverage
                if pred_h.pi_lower_80 is not None and pred_h.pi_upper_80 is not None:
                    if pred_h.pi_lower_80 <= y_actual <= pred_h.pi_upper_80:
                        coverage_hits += 1

            if valid_samples > 0:
                err_arr = np.array(errors)
                clim_arr = np.array(clim_errors)

                mae = float(np.mean(np.abs(err_arr)))
                mse = float(np.mean(err_arr ** 2))
                rmse = float(np.sqrt(mse))
                mbe = float(np.mean(err_arr))
                coverage = float(coverage_hits / valid_samples)

                clim_mse = float(np.mean(clim_arr ** 2))
                skill = float(1.0 - (mse / clim_mse)) if clim_mse > 0 else 0.0

                horizon_results[h] = HorizonEvaluationMetrics(
                    horizon_hours=h,
                    sample_count=valid_samples,
                    mae=mae,
                    rmse=rmse,
                    mbe=mbe,
                    coverage_80=coverage,
                    skill_score_vs_mean=skill,
                )

        return ForecastVerificationReport(
            model_name="PERSISTENCE_BASELINE",
            target_variable=target_variable,
            evaluation_start=test_timestamps[0],
            evaluation_end=test_timestamps[-1],
            horizon_metrics=horizon_results,
        )
