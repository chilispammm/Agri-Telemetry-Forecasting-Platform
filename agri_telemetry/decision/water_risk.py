"""
Uncertainty-Aware Water Risk & Agronomic Threshold Evaluator.
Integrates empirical uncertainty distributions and multi-horizon forward trajectories.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.domain.enums import AlertCategory, AlertSeverity, ThresholdType
from agri_telemetry.contracts.alert_event import AlertEvent, TriggerCondition, AlertContext
from agri_telemetry.decision.taxonomy import RiskCertaintyLevel
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator
from agri_telemetry.forecasting.uncertainty_calibration import RegimeConditionedCalibrator


@dataclass
class WaterRiskConfig:
    """Configurable risk evaluation parameters."""
    d_mad: float = 0.50                         # Management Allowable Depletion (configured demonstration threshold)
    critical_wilting_depletion: float = 0.85    # Critical wilting threshold (fraction of TAW)
    tau_risk: float = 0.70                      # Minimum exceedance probability to trigger early warning
    crop_type: str = "Maize"
    growth_stage: str = "Vegetative"
    max_calibrated_horizon_hours: int = 48      # Horizons > 48h classified as HIGHLY_UNCERTAIN under in-situ


class UncertaintyAwareRiskEvaluator:
    """
    Evaluates Tier-3 Agronomic Risks on valid SoilWaterState records and forward forecasts.
    Guarantees strict advisory-only non-actuating alerts.
    """

    def __init__(
        self,
        config: Optional[WaterRiskConfig] = None,
        calibrator: Optional[Any] = None,
    ):
        self.config = config or WaterRiskConfig()
        self.calibrator = calibrator

    def classify_forecast_risk_certainty(
        self,
        point_forecast: float,
        horizon_hours: int,
        interval_80: Optional[Tuple[float, float]] = None,
        exceedance_p: Optional[float] = None,
    ) -> RiskCertaintyLevel:
        """
        Classifies risk certainty based on point forecast, prediction intervals, and horizon boundaries.
        """
        threshold = self.config.d_mad

        # Extended horizons (> 48h) with purely in-situ models have growing uncalibrated spread
        if horizon_hours > self.config.max_calibrated_horizon_hours:
            if interval_80 and (interval_80[0] <= threshold <= interval_80[1] or point_forecast >= threshold):
                return RiskCertaintyLevel.HIGHLY_UNCERTAIN

        if interval_80 is not None:
            lower, upper = interval_80
            if upper < threshold:
                return RiskCertaintyLevel.DEFINITELY_NOT_REACHED
            elif point_forecast < threshold <= upper:
                return RiskCertaintyLevel.PLAUSIBLY_REACHED
            else:
                return RiskCertaintyLevel.LIKELY_REACHED

        if exceedance_p is not None:
            if exceedance_p < 0.20:
                return RiskCertaintyLevel.DEFINITELY_NOT_REACHED
            elif exceedance_p < self.config.tau_risk:
                return RiskCertaintyLevel.PLAUSIBLY_REACHED
            else:
                return RiskCertaintyLevel.LIKELY_REACHED

        # Fallback point-estimate logic
        if point_forecast >= threshold:
            return RiskCertaintyLevel.LIKELY_REACHED
        return RiskCertaintyLevel.DEFINITELY_NOT_REACHED

    def evaluate_state_and_forecast(
        self,
        state: SoilWaterState,
        forecast_horizons: Optional[List[int]] = None,
        forecast_predictions: Optional[Dict[int, Dict[str, Any]]] = None,
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
                    f"CRITICAL AGRONOMIC RISK: Root-zone soil moisture depletion ({state.depletion_fraction:.1%}) "
                    f"has breached critical wilting threshold ({self.config.critical_wilting_depletion:.1%}). "
                    "Severe crop water stress imminent. Urgent irrigation review required."
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
                    f"AGRONOMIC RISK: Root-zone depletion ({state.depletion_fraction:.1%}) has crossed "
                    f"Management Allowable Depletion threshold ({self.config.d_mad:.1%}). "
                    "Irrigation replenishment recommended to prevent yield penalty."
                ),
            )
            alerts.append(alert)

        # 3. Probabilistic Forward-Looking Forecast Risk Check
        elif state.depletion_fraction < self.config.d_mad:
            for h in horizons:
                exceedance_p = None
                interval_80 = None
                point_fc = state.depletion_fraction

                # Extract provided forward prediction details if available
                if forecast_predictions and h in forecast_predictions:
                    pred_info = forecast_predictions[h]
                    point_fc = pred_info.get("point_forecast", state.depletion_fraction)
                    interval_80 = pred_info.get("interval_80")
                    exceedance_p = pred_info.get("exceedance_probability")

                # Fallback to calibrator estimation if not explicitly provided
                if exceedance_p is None and self.calibrator is not None:
                    if hasattr(self.calibrator, "estimate_exceedance_probability"):
                        exceedance_p = self.calibrator.estimate_exceedance_probability(
                            point_forecast=point_fc,
                            horizon_hours=h,
                            threshold_value=self.config.d_mad,
                        )

                certainty = self.classify_forecast_risk_certainty(
                    point_forecast=point_fc,
                    horizon_hours=h,
                    interval_80=interval_80,
                    exceedance_p=exceedance_p,
                )

                # Trigger early warning if confidence threshold is met
                is_trigger = (exceedance_p is not None and exceedance_p >= self.config.tau_risk) or (
                    certainty in (RiskCertaintyLevel.LIKELY_REACHED, RiskCertaintyLevel.PLAUSIBLY_REACHED)
                    and point_fc >= self.config.d_mad * 0.95
                )

                if is_trigger:
                    certainty_str = certainty.value
                    prob_val = round(exceedance_p, 4) if exceedance_p is not None else 0.75
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
                            exceedance_probability=prob_val,
                            predicted_value=round(point_fc, 4),
                        ),
                        context=AlertContext(
                            crop_type=self.config.crop_type,
                            growth_stage=self.config.growth_stage,
                            current_depletion_fraction=round(state.depletion_fraction, 4),
                            forecast_model_id=f"UNCERTAINTY_AWARE_H{h}",
                            qc_failure_reason=f"Risk Certainty: {certainty_str}",
                        ),
                        actionable_guidance=(
                            f"EARLY RISK ADVISORY [{certainty_str}]: Depletion predicted to cross "
                            f"{self.config.d_mad:.0%} MAD at +{h}h (P = {prob_val:.1%}). "
                            "Prepare irrigation application schedule."
                        ),
                    )
                    alerts.append(alert)
                    break  # Emit alert for earliest horizon only

        return alerts
