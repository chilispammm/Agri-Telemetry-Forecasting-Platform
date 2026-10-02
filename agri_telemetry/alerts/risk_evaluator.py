"""
Agronomic Risk Evaluator.
Evaluates Management Allowable Depletion and Wilting Proximity risks under calibrated uncertainty.
"""

from datetime import datetime
from typing import List, Optional

from agri_telemetry.contracts.alert_event import (
    AlertEvent,
    TriggerCondition,
    AlertContext,
)
from agri_telemetry.domain.enums import (
    AlertCategory,
    AlertSeverity,
    ThresholdType,
)
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.alerts.config import RiskEvaluationConfig
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator


class AgronomicRiskEvaluator:
    """
    Evaluates Tier-3 Agronomic Risks on valid soil water states and probabilistic forecasts.
    Guarantees strict advisory-only non-actuating alerts.
    """

    def __init__(
        self,
        config: Optional[RiskEvaluationConfig] = None,
        calibrator: Optional[EmpiricalUncertaintyCalibrator] = None,
    ):
        self.config = config or RiskEvaluationConfig()
        self.calibrator = calibrator

    def evaluate_state_and_forecast(
        self,
        state: SoilWaterState,
        forecast_horizons: Optional[List[int]] = None,
    ) -> List[AlertEvent]:
        """
        Evaluates real-time state and forward-looking forecast horizons for agronomic threshold crossings.
        """
        # Strict isolation: Do not evaluate agronomic risk on invalid/quarantined states
        if not state.is_valid:
            return []

        alerts: List[AlertEvent] = []
        horizons = forecast_horizons or [1, 6, 12, 24, 48, 72, 168]

        # 1. Real-time Critical Wilting Proximity Check (Highest Severity)
        if state.depletion_fraction >= self.config.critical_wilting_depletion:
            alert = AlertEvent.create_new(
                category=AlertCategory.AGRONOMIC_RISK,
                severity=AlertSeverity.CRITICAL,
                source_id=state.source_id,
                site_id=state.site_id,
                trigger_time=state.timestamp,
                trigger_condition=TriggerCondition(
                    threshold_type=ThresholdType.CRITICAL_WILTING_PROXIMITY,
                    threshold_value=self.config.critical_wilting_depletion,
                    threshold_unit="fraction",
                    predicted_value=round(state.depletion_fraction, 4),
                ),
                context=AlertContext(
                    crop_type=self.config.crop_type,
                    growth_stage=self.config.growth_stage,
                    current_depletion_fraction=round(state.depletion_fraction, 4),
                ),
                actionable_guidance=(
                    f"CRITICAL AGRONOMIC RISK ADVISORY: Root-zone soil moisture depletion ({state.depletion_fraction:.1%}) "
                    f"has breached critical wilting threshold ({self.config.critical_wilting_depletion:.1%}). "
                    "Severe crop water stress indicated. Review field soil-water conditions."
                ),
            )
            alerts.append(alert)

        # 2. Real-time Management Allowable Depletion (MAD) Check
        elif state.depletion_fraction >= self.config.d_mad:
            alert = AlertEvent.create_new(
                category=AlertCategory.AGRONOMIC_RISK,
                severity=AlertSeverity.WARNING,
                source_id=state.source_id,
                site_id=state.site_id,
                trigger_time=state.timestamp,
                trigger_condition=TriggerCondition(
                    threshold_type=ThresholdType.MANAGEMENT_ALLOWABLE_DEPLETION,
                    threshold_value=self.config.d_mad,
                    threshold_unit="fraction",
                    predicted_value=round(state.depletion_fraction, 4),
                ),
                context=AlertContext(
                    crop_type=self.config.crop_type,
                    growth_stage=self.config.growth_stage,
                    current_depletion_fraction=round(state.depletion_fraction, 4),
                ),
                actionable_guidance=(
                    f"AGRONOMIC RISK ADVISORY: Root-zone depletion ({state.depletion_fraction:.1%}) has crossed "
                    f"configured Management Allowable Depletion threshold ({self.config.d_mad:.1%}). "
                    "Review irrigation planning and crop water status."
                ),
            )
            alerts.append(alert)

        # 3. Probabilistic Forward-Looking Forecast Risk Check
        if self.calibrator and self.calibrator.is_calibrated:
            for h in horizons:
                # Estimate P(Dr_{t+h} >= d_mad)
                exceedance_p = self.calibrator.estimate_exceedance_probability(
                    point_forecast=state.depletion_fraction,
                    horizon_hours=h,
                    threshold_value=self.config.d_mad,
                )

                if exceedance_p >= self.config.tau_risk and state.depletion_fraction < self.config.d_mad:
                    # Emitted only if not already breached in real-time
                    alert = AlertEvent.create_new(
                        category=AlertCategory.AGRONOMIC_RISK,
                        severity=AlertSeverity.WARNING,
                        source_id=state.source_id,
                        site_id=state.site_id,
                        trigger_time=state.timestamp,
                        trigger_condition=TriggerCondition(
                            threshold_type=ThresholdType.MANAGEMENT_ALLOWABLE_DEPLETION,
                            threshold_value=self.config.d_mad,
                            threshold_unit="fraction",
                            forecast_horizon_hours=h,
                            exceedance_probability=round(exceedance_p, 4),
                            predicted_value=round(state.depletion_fraction, 4),
                        ),
                        context=AlertContext(
                            crop_type=self.config.crop_type,
                            growth_stage=self.config.growth_stage,
                            current_depletion_fraction=round(state.depletion_fraction, 4),
                            forecast_model_id="PERSISTENCE_BASELINE",
                        ),
                        actionable_guidance=(
                            f"EARLY RISK ADVISORY: Depletion predicted to exceed {self.config.d_mad:.0%} MAD threshold "
                            f"within {h} hours (Exceedance Probability P = {exceedance_p:.1%}). "
                            "Review irrigation planning and weather forecast."
                        ),
                    )
                    alerts.append(alert)
                    break  # Emit alert for the earliest horizon trigger to prevent alert flood

        return alerts
