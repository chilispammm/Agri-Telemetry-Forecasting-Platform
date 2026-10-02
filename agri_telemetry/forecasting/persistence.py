"""
Persistence Forecast Benchmark Model.
Evaluates the mandatory baseline: Y_hat_{t+h|t} = Y_t across configured horizons.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from agri_telemetry.domain.models import ForecastHorizonPrediction
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator


class PersistenceModel:
    """
    Mandatory baseline benchmark model for soil moisture forecasting.
    Equation: Y_hat_{t+h|t} = Y_t
    """

    def __init__(
        self,
        horizons: Optional[List[int]] = None,
        calibrator: Optional[EmpiricalUncertaintyCalibrator] = None,
        model_name: str = "PERSISTENCE_BASELINE",
        model_version: str = "1.0.0",
    ):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.calibrator = calibrator or EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        self.model_name = model_name
        self.model_version = model_version

    def predict(
        self,
        current_value: float,
        origin_time: Optional[datetime] = None,
        unit: str = "m3/m3",
        min_bound: float = 0.0,
        max_bound: float = 0.60,
    ) -> List[ForecastHorizonPrediction]:
        """
        Generates persistence point forecasts and calibrated prediction intervals for all horizons.
        """
        predictions: List[ForecastHorizonPrediction] = []
        orig = origin_time or datetime.utcnow()

        for h in self.horizons:
            valid_dt = orig + timedelta(hours=h)

            point = float(current_value)

            quantiles = self.calibrator.calculate_quantiles(
                point_forecast=point,
                horizon_hours=h,
                min_bound=min_bound,
                max_bound=max_bound,
            )

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
                    pi_lower_80=quantiles["q10"],
                    pi_upper_80=quantiles["q90"],
                )
            )

        return predictions
