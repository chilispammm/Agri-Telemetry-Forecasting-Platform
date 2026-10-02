"""
Phase 3 Operational Advisory Engine.
Integrates Tier-1 Data Quality QC, Tier-2 Physical Deviation Intelligence, Tier-3 Water Risk Evaluation,
and Alert Persistence Filtering into a unified decision-support pipeline.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime

from agri_telemetry.contracts.telemetry_event import TelemetryEvent
from agri_telemetry.contracts.forecast_event import ForecastEvent
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.domain.enums import AlertCategory, AlertSeverity, VariableName
from agri_telemetry.qc.engine import Tier1QCEngine
from agri_telemetry.decision.taxonomy import (
    AnomalyClassification,
    AnomalyAssessment,
    RiskCertaintyLevel,
    PersistenceStatus,
)
from agri_telemetry.decision.physical_deviation import (
    PhysicalDeviationDetector,
    PhysicalDeviationConfig,
)
from agri_telemetry.decision.water_risk import (
    UncertaintyAwareRiskEvaluator,
    WaterRiskConfig,
)
from agri_telemetry.decision.persistence_filter import (
    AlertPersistenceFilter,
    PersistenceFilterConfig,
)


@dataclass
class DecisionCycleResult:
    """Complete output of a single operational decision cycle."""
    timestamp: str
    is_quarantined: bool
    classification: AnomalyClassification
    primary_reason: str
    raw_candidate_alerts: List[AlertEvent] = field(default_factory=list)
    confirmed_advisories: List[AlertEvent] = field(default_factory=list)
    assessments: List[AnomalyAssessment] = field(default_factory=list)


class OperationalAdvisoryEngine:
    """
    Unified Operational Advisory Engine for Phase 3.
    Strictly isolates data-quality faults from agronomic risk and controls alert burden via persistence filtering.
    """

    def __init__(
        self,
        qc_engine: Optional[Tier1QCEngine] = None,
        deviation_detector: Optional[PhysicalDeviationDetector] = None,
        risk_evaluator: Optional[UncertaintyAwareRiskEvaluator] = None,
        persistence_filter: Optional[AlertPersistenceFilter] = None,
        apply_persistence_filter: bool = True,
    ):
        self.qc_engine = qc_engine or Tier1QCEngine()
        self.deviation_detector = deviation_detector or PhysicalDeviationDetector()
        self.risk_evaluator = risk_evaluator or UncertaintyAwareRiskEvaluator()
        self.persistence_filter = persistence_filter or AlertPersistenceFilter()
        self.apply_persistence_filter = apply_persistence_filter

    def process_cycle(
        self,
        event: TelemetryEvent,
        state: Optional[SoilWaterState] = None,
        forecast_predictions: Optional[Dict[int, Dict[str, Any]]] = None,
        forecast_1h_prior: Optional[float] = None,
        precipitation_mm: Optional[float] = None,
    ) -> DecisionCycleResult:
        """
        Executes a single end-to-end advisory decision cycle.
        """
        candidate_alerts: List[AlertEvent] = []
        assessments: List[AnomalyAssessment] = []

        # 1. Tier-1 Quality Control & Ingress Validation
        evaluated_event, is_quarantined, qc_alert = self.qc_engine.evaluate_event(event)
        if qc_alert:
            candidate_alerts.append(qc_alert)
            assessments.append(
                AnomalyAssessment(
                    classification=AnomalyClassification.DATA_QUALITY_ANOMALY,
                    primary_reason=qc_alert.actionable_guidance,
                    is_quarantined=True,
                    requires_operator_review=True,
                    details={"alert_id": qc_alert.alert_id},
                )
            )

        # If data is quarantined, STOP downstream physical and agronomic evaluation for this step
        if is_quarantined:
            confirmed = (
                self.persistence_filter.filter_alerts(candidate_alerts)
                if self.apply_persistence_filter
                else candidate_alerts
            )
            return DecisionCycleResult(
                timestamp=event.event_time,
                is_quarantined=True,
                classification=AnomalyClassification.DATA_QUALITY_ANOMALY,
                primary_reason=qc_alert.actionable_guidance if qc_alert else "Data quality quarantine",
                raw_candidate_alerts=candidate_alerts,
                confirmed_advisories=confirmed,
                assessments=assessments,
            )

        # 2. Extract collocated precipitation if available
        precip_val = precipitation_mm
        if precip_val is None:
            for m in event.measurements:
                if m.variable_name == VariableName.PRECIPITATION and m.value is not None:
                    precip_val = m.value
                    break
        if precip_val is not None:
            self.deviation_detector.record_precipitation(precip_val)

        # 3. Feed prior 1-hour forecast expectation if provided
        if forecast_1h_prior is not None:
            self.deviation_detector.record_prior_forecast(forecast_1h_prior)

        # 4. Tier-2 Physical Deviation Intelligence (only on valid state)
        if state is not None and state.is_valid:
            dev_alerts = self.deviation_detector.evaluate(state)
            for da in dev_alerts:
                candidate_alerts.append(da)
                assessments.append(
                    AnomalyAssessment(
                        classification=AnomalyClassification.PHYSICAL_DEVIATION,
                        primary_reason=da.actionable_guidance,
                        is_quarantined=False,
                        requires_operator_review=True,
                        details={"alert_id": da.alert_id},
                    )
                )

            # 5. Tier-3 Agronomic & Water Risk Evaluation
            risk_alerts = self.risk_evaluator.evaluate_state_and_forecast(
                state=state,
                forecast_predictions=forecast_predictions,
            )
            for ra in risk_alerts:
                candidate_alerts.append(ra)
                assessments.append(
                    AnomalyAssessment(
                        classification=AnomalyClassification.OPERATIONAL_WATER_RISK,
                        primary_reason=ra.actionable_guidance,
                        is_quarantined=False,
                        requires_operator_review=True,
                        details={"alert_id": ra.alert_id},
                    )
                )

        # 6. Apply Alert Persistence Filtering
        confirmed_advisories = (
            self.persistence_filter.filter_alerts(candidate_alerts)
            if self.apply_persistence_filter
            else candidate_alerts
        )

        # Determine overall classification
        classification = AnomalyClassification.NORMAL_OPERATION
        primary_reason = "Nominal operation within expected limits."
        if any(a.category == AlertCategory.AGRONOMIC_RISK for a in confirmed_advisories):
            classification = AnomalyClassification.OPERATIONAL_WATER_RISK
            primary_reason = "Confirmed operational water deficit risk."
        elif any(a.category == AlertCategory.PHYSICAL_DEVIATION for a in confirmed_advisories):
            classification = AnomalyClassification.PHYSICAL_DEVIATION
            primary_reason = "Confirmed physical or forecast deviation."

        return DecisionCycleResult(
            timestamp=event.event_time,
            is_quarantined=False,
            classification=classification,
            primary_reason=primary_reason,
            raw_candidate_alerts=candidate_alerts,
            confirmed_advisories=confirmed_advisories,
            assessments=assessments,
        )

    def reset(self) -> None:
        """Resets state across all pipeline sub-engines."""
        self.qc_engine.reset()
        self.deviation_detector.reset()
        self.persistence_filter.reset()
