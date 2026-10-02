"""
Physical Deviation Intelligence Engine.
Detects departures from expected hydrological and thermodynamic behavior.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.domain.enums import AlertCategory, AlertSeverity, ThresholdType
from agri_telemetry.contracts.alert_event import AlertEvent, TriggerCondition, AlertContext
from agri_telemetry.decision.taxonomy import PhysicalDeviationType


@dataclass
class PhysicalDeviationConfig:
    """Configurable thresholds for physical deviation detection."""
    max_forecast_residual: float = 0.020        # m3/m3 residual threshold for 1-hour forecast
    max_hourly_drying_rate: float = 0.025       # m3/m3/hr max physical drying rate without drainage
    min_unexplained_wetting_delta: float = 0.015 # m3/m3/hr wetting threshold without rain
    precip_tolerance_mm: float = 0.2            # mm rain threshold below which wetting is unexplained
    deep_inversion_delta: float = 0.015         # m3/m3/hr deep sensor jump without shallow wetting


class PhysicalDeviationDetector:
    """
    Evaluates physical consistency of incoming soil-water telemetry against physical laws
    and prior forecast expectations.
    """

    def __init__(self, config: Optional[PhysicalDeviationConfig] = None):
        self.config = config or PhysicalDeviationConfig()
        self._prev_state: Optional[SoilWaterState] = None
        self._prev_forecast_1h: Optional[float] = None
        self._last_precip_mm: float = 0.0

    def record_prior_forecast(self, forecast_1h_vwc: float) -> None:
        """Stores the 1-step ahead forecast to evaluate against next observation."""
        self._prev_forecast_1h = forecast_1h_vwc

    def record_precipitation(self, precip_mm: float) -> None:
        """Stores the collocated precipitation measurement."""
        self._last_precip_mm = max(0.0, precip_mm)

    def evaluate(self, state: SoilWaterState) -> List[AlertEvent]:
        """
        Evaluates a valid SoilWaterState for physical deviations.
        Returns a list of AlertEvent (Category: PHYSICAL_DEVIATION).
        """
        if not state.is_valid:
            return []

        alerts: List[AlertEvent] = []

        # 1. 1-Step Forecast Residual Breach
        if self._prev_forecast_1h is not None:
            residual = abs(state.theta_rz - self._prev_forecast_1h)
            if residual > self.config.max_forecast_residual:
                alerts.append(
                    AlertEvent.create_new(
                        category=AlertCategory.PHYSICAL_DEVIATION,
                        severity=AlertSeverity.WARNING,
                        source_id=state.source_id,
                        site_id=state.site_id,
                        trigger_time=state.timestamp,
                        trigger_condition=TriggerCondition(
                            threshold_type=ThresholdType.MASS_BALANCE_RESIDUAL,
                            threshold_value=self.config.max_forecast_residual,
                            threshold_unit="m3/m3",
                            forecast_horizon_hours=1,
                            predicted_value=round(residual, 4),
                        ),
                        context=AlertContext(
                            current_depletion_fraction=round(state.depletion_fraction, 4),
                            forecast_model_id="PRIOR_1H_STEP",
                            qc_failure_reason=f"Residual |y_t - y_hat| = {residual:.4f} > {self.config.max_forecast_residual:.4f} m3/m3",
                        ),
                        actionable_guidance=(
                            f"PHYSICAL DEVIATION: Root-zone moisture ({state.theta_rz:.4f} m3/m3) deviated "
                            f"from 1-hour forecast ({self._prev_forecast_1h:.4f} m3/m3) by {residual:.4f} m3/m3. "
                            "Inspect for unexpected hydrological event, unmetered irrigation, or microclimate anomaly."
                        ),
                    )
                )

        # 2. Stateful Physical Rate-of-Change Checks (if previous state exists)
        if self._prev_state is not None:
            delta_vwc = state.theta_rz - self._prev_state.theta_rz

            # 2a. Unphysical Drying Rate
            if delta_vwc < -self.config.max_hourly_drying_rate and state.theta_rz < state.theta_sat:
                alerts.append(
                    AlertEvent.create_new(
                        category=AlertCategory.PHYSICAL_DEVIATION,
                        severity=AlertSeverity.WARNING,
                        source_id=state.source_id,
                        site_id=state.site_id,
                        trigger_time=state.timestamp,
                        trigger_condition=TriggerCondition(
                            threshold_type=ThresholdType.MASS_BALANCE_RESIDUAL,
                            threshold_value=self.config.max_hourly_drying_rate,
                            threshold_unit="m3/m3/hr",
                            predicted_value=round(abs(delta_vwc), 4),
                        ),
                        context=AlertContext(
                            current_depletion_fraction=round(state.depletion_fraction, 4),
                            qc_failure_reason=f"Unphysical drying rate delta = {delta_vwc:.4f} m3/m3/hr",
                        ),
                        actionable_guidance=(
                            f"PHYSICAL DEVIATION: Rapid soil drying of {abs(delta_vwc):.4f} m3/m3/hr exceeds "
                            f"maximum physical ET rate ({self.config.max_hourly_drying_rate:.4f} m3/m3/hr). "
                            "Check for sudden sensor settling, root shearing, or preferential macropore drainage."
                        ),
                    )
                )

            # 2b. Unexplained Infiltration (Wetting without Rain)
            if delta_vwc > self.config.min_unexplained_wetting_delta and self._last_precip_mm <= self.config.precip_tolerance_mm:
                alerts.append(
                    AlertEvent.create_new(
                        category=AlertCategory.PHYSICAL_DEVIATION,
                        severity=AlertSeverity.INFO,
                        source_id=state.source_id,
                        site_id=state.site_id,
                        trigger_time=state.timestamp,
                        trigger_condition=TriggerCondition(
                            threshold_type=ThresholdType.MASS_BALANCE_RESIDUAL,
                            threshold_value=self.config.min_unexplained_wetting_delta,
                            threshold_unit="m3/m3/hr",
                            predicted_value=round(delta_vwc, 4),
                        ),
                        context=AlertContext(
                            current_depletion_fraction=round(state.depletion_fraction, 4),
                            qc_failure_reason=f"Unexplained wetting +{delta_vwc:.4f} m3/m3 with P={self._last_precip_mm:.1f}mm",
                        ),
                        actionable_guidance=(
                            f"PHYSICAL DEVIATION: Significant root-zone wetting (+{delta_vwc:.4f} m3/m3/hr) observed "
                            f"without recorded precipitation (P={self._last_precip_mm:.1f}mm). "
                            "Likely unrecorded irrigation event, groundwater recharge, or surface run-on."
                        ),
                    )
                )

            # 2c. Hydraulic Inversion (Deep wetting before shallow)
            if state.depth_vwc and self._prev_state.depth_vwc:
                shallow_keys = [d for d in state.depth_vwc.keys() if d <= 10.0]
                deep_keys = [d for d in state.depth_vwc.keys() if d >= 50.0]

                if shallow_keys and deep_keys:
                    shallow_delta = max((state.depth_vwc[d] - self._prev_state.depth_vwc.get(d, state.depth_vwc[d])) for d in shallow_keys)
                    deep_delta = max((state.depth_vwc[d] - self._prev_state.depth_vwc.get(d, state.depth_vwc[d])) for d in deep_keys)

                    if deep_delta > self.config.deep_inversion_delta and shallow_delta < 0.005:
                        alerts.append(
                            AlertEvent.create_new(
                                category=AlertCategory.PHYSICAL_DEVIATION,
                                severity=AlertSeverity.INFO,
                                source_id=state.source_id,
                                site_id=state.site_id,
                                trigger_time=state.timestamp,
                                trigger_condition=TriggerCondition(
                                    threshold_type=ThresholdType.MASS_BALANCE_RESIDUAL,
                                    threshold_value=self.config.deep_inversion_delta,
                                    threshold_unit="m3/m3/hr",
                                    predicted_value=round(deep_delta, 4),
                                ),
                                context=AlertContext(
                                    current_depletion_fraction=round(state.depletion_fraction, 4),
                                    qc_failure_reason=f"Deep soil wetting (+{deep_delta:.4f}) without shallow wetting (+{shallow_delta:.4f})",
                                ),
                                actionable_guidance=(
                                    f"PHYSICAL DEVIATION: Hydraulic inversion detected. Deep soil (>50cm) wetted (+{deep_delta:.4f} m3/m3) "
                                    f"without surface layer wetting (+{shallow_delta:.4f} m3/m3). "
                                    "Suggests lateral subsurface flow, rising water table, or sub-surface drip irrigation."
                                ),
                            )
                        )

        # Update state cache
        self._prev_state = state
        self._prev_forecast_1h = None  # Reset 1h forecast slot after consumption

        return alerts

    def reset(self) -> None:
        """Resets state cache."""
        self._prev_state = None
        self._prev_forecast_1h = None
        self._last_precip_mm = 0.0
