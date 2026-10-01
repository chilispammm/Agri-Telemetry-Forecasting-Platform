"""
Forecasting Engine.
Orchestrates baseline inference and emits canonical ForecastEvents.
"""

from datetime import datetime
from typing import List, Optional

from agri_telemetry.contracts.forecast_event import (
    ForecastEvent,
    HorizonPrediction,
    Quantiles,
    PredictionInterval80,
)
from agri_telemetry.domain.enums import TargetVariable
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.forecasting.persistence import PersistenceModel
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator


class ForecastingEngine:
    """
    Forecasting Engine for soil-water state predictions.
    Emits schema-validated ForecastEvents.
    """

    def __init__(
        self,
        model: Optional[PersistenceModel] = None,
        calibrator: Optional[EmpiricalUncertaintyCalibrator] = None,
        horizons: Optional[List[int]] = None,
    ):
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.calibrator = calibrator or EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        self.model = model or PersistenceModel(horizons=self.horizons, calibrator=self.calibrator)

    def generate_forecast(
        self,
        state: SoilWaterState,
        target_variable: TargetVariable = TargetVariable.VOLUMETRIC_WATER_CONTENT,
        random_seed: int = 42,
    ) -> ForecastEvent:
        """
        Generates point forecasts and uncertainty intervals for the given state, emitting a ForecastEvent.
        """
        if target_variable == TargetVariable.VOLUMETRIC_WATER_CONTENT:
            val = state.theta_rz
            unit_str = "m3/m3"
            min_b, max_b = 0.0, 0.60
        elif target_variable == TargetVariable.ROOT_ZONE_DEPLETION_FRACTION:
            val = state.depletion_fraction
            unit_str = "fraction"
            min_b, max_b = -0.50, 1.50
        elif target_variable == TargetVariable.ROOT_ZONE_STORAGE_MM:
            val = state.storage_mm
            unit_str = "mm"
            min_b, max_b = 0.0, 600.0
        else:
            val = state.available_water_fraction
            unit_str = "fraction"
            min_b, max_b = -0.50, 1.50

        internal_preds = self.model.predict(
            current_value=val,
            origin_time=state.timestamp,
            unit=unit_str,
            min_bound=min_b,
            max_bound=max_b,
        )

        contract_preds: List[HorizonPrediction] = []
        for p in internal_preds:
            contract_preds.append(
                HorizonPrediction(
                    horizon_hours=p.horizon_hours,
                    valid_time=p.target_time.isoformat().replace("+00:00", "Z") if p.target_time.tzinfo else f"{p.target_time.isoformat()}Z",
                    point_forecast=round(p.point_forecast, 4),
                    quantiles=Quantiles(
                        q10=round(p.q10, 4) if p.q10 is not None else None,
                        q25=round(p.q25, 4) if p.q25 is not None else None,
                        q50=round(p.q50, 4) if p.q50 is not None else None,
                        q75=round(p.q75, 4) if p.q75 is not None else None,
                        q90=round(p.q90, 4) if p.q90 is not None else None,
                    ),
                    prediction_interval_80=PredictionInterval80(
                        lower=round(p.pi_lower_80, 4) if p.pi_lower_80 is not None else round(p.point_forecast, 4),
                        upper=round(p.pi_upper_80, 4) if p.pi_upper_80 is not None else round(p.point_forecast, 4),
                    ),
                    unit=unit_str,
                )
            )

        return ForecastEvent.create_new(
            source_id=state.source_id,
            site_id=state.site_id,
            forecast_origin_time=state.timestamp,
            target_variable=target_variable,
            model_name=self.model.model_name,
            model_version=self.model.model_version,
            predictions=contract_preds,
            target_depth_range_cm=[0.0, state.root_depth_cm],
            random_seed=random_seed,
        )
