"""
Alert Persistence & False-Alert Filtering Engine.
Implements N-of-M sliding window and consecutive confirmation filters to suppress transient noise.
"""

from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime

from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.domain.enums import AlertCategory, AlertSeverity, ThresholdType
from agri_telemetry.decision.taxonomy import PersistenceStatus


@dataclass
class PersistenceFilterConfig:
    """Configuration for alert persistence logic."""
    mode: str = "consecutive"        # "consecutive" or "n_of_m"
    consecutive_steps: int = 2       # k consecutive steps required to confirm alert
    n_required: int = 3              # N required for N-of-M mode
    m_window: int = 5                # M window length for N-of-M mode
    pass_critical_immediately: bool = True  # If True, CRITICAL alerts bypass persistence delay for safety


@dataclass
class AlertTrackerState:
    """Internal state tracking for an alert condition key."""
    consecutive_count: int = 0
    history_window: deque = field(default_factory=lambda: deque(maxlen=10))
    status: PersistenceStatus = PersistenceStatus.PENDING_CONFIRMATION
    first_triggered_time: Optional[str] = None
    last_confirmed_time: Optional[str] = None
    suppressed_count: int = 0
    emitted_count: int = 0


class AlertPersistenceFilter:
    """
    Stateful persistence filter that prevents single-observation noise from triggering operational alerts.
    """

    def __init__(self, config: Optional[PersistenceFilterConfig] = None):
        self.config = config or PersistenceFilterConfig()
        # Key: (source_id, category, threshold_type) -> AlertTrackerState
        self._trackers: Dict[Tuple[str, str, str], AlertTrackerState] = defaultdict(
            lambda: AlertTrackerState(history_window=deque(maxlen=self.config.m_window))
        )
        self.total_candidates_processed: int = 0
        self.total_transient_suppressed: int = 0
        self.total_confirmed_emitted: int = 0

    def _get_key(self, alert: AlertEvent) -> Tuple[str, str, str]:
        category_str = alert.category.value if hasattr(alert.category, "value") else str(alert.category)
        threshold_str = (
            alert.trigger_condition.threshold_type.value
            if hasattr(alert.trigger_condition.threshold_type, "value")
            else str(alert.trigger_condition.threshold_type)
        )
        return (alert.source_id, category_str, threshold_str)

    def filter_alerts(
        self,
        candidate_alerts: List[AlertEvent],
        active_source_ids: Optional[List[str]] = None,
    ) -> List[AlertEvent]:
        """
        Filters incoming candidate alerts against persistence criteria.
        Returns only confirmed AlertEvent objects.
        """
        confirmed_alerts: List[AlertEvent] = []
        triggered_keys: Set[Tuple[str, str, str]] = set()

        for alert in candidate_alerts:
            self.total_candidates_processed += 1
            key = self._get_key(alert)
            triggered_keys.add(key)
            tracker = self._trackers[key]

            # Critical alerts can optionally bypass persistence filter for immediate safety
            if self.config.pass_critical_immediately and alert.severity == AlertSeverity.CRITICAL:
                tracker.status = PersistenceStatus.CONFIRMED
                tracker.emitted_count += 1
                self.total_confirmed_emitted += 1
                confirmed_alerts.append(alert)
                continue

            # Update tracking state
            tracker.consecutive_count += 1
            tracker.history_window.append(True)
            if tracker.first_triggered_time is None:
                tracker.first_triggered_time = alert.trigger_time

            is_confirmed = False
            confirmation_meta = ""

            if self.config.mode == "consecutive":
                if tracker.consecutive_count >= self.config.consecutive_steps:
                    is_confirmed = True
                    confirmation_meta = f"[Confirmed: {tracker.consecutive_count} consecutive steps]"
            elif self.config.mode == "n_of_m":
                n_trues = sum(1 for x in tracker.history_window if x)
                if n_trues >= self.config.n_required:
                    is_confirmed = True
                    confirmation_meta = f"[Confirmed: {n_trues}/{len(tracker.history_window)} in window]"

            if is_confirmed:
                tracker.status = PersistenceStatus.CONFIRMED
                tracker.last_confirmed_time = alert.trigger_time
                tracker.emitted_count += 1
                self.total_confirmed_emitted += 1

                # Annotate actionable guidance with persistence confirmation
                annotated_guidance = f"{confirmation_meta} {alert.actionable_guidance}"
                confirmed_alert = AlertEvent(
                    schema_version=alert.schema_version,
                    alert_id=alert.alert_id,
                    category=alert.category,
                    severity=alert.severity,
                    source_id=alert.source_id,
                    site_id=alert.site_id,
                    trigger_time=alert.trigger_time,
                    trigger_condition=alert.trigger_condition,
                    context=alert.context,
                    actionable_guidance=annotated_guidance,
                    is_autonomous_actuation=False,
                )
                confirmed_alerts.append(confirmed_alert)
            else:
                tracker.status = PersistenceStatus.PENDING_CONFIRMATION
                tracker.suppressed_count += 1
                self.total_transient_suppressed += 1

        # Age out non-triggered keys
        for key, tracker in list(self._trackers.items()):
            if key not in triggered_keys:
                tracker.consecutive_count = 0
                tracker.history_window.append(False)
                if tracker.status == PersistenceStatus.CONFIRMED:
                    tracker.status = PersistenceStatus.RESOLVED

        return confirmed_alerts

    def get_stats(self) -> Dict[str, int]:
        """Returns summary statistics on filtering efficacy."""
        return {
            "total_candidates_processed": self.total_candidates_processed,
            "total_transient_suppressed": self.total_transient_suppressed,
            "total_confirmed_emitted": self.total_confirmed_emitted,
            "active_trackers_count": len(self._trackers),
        }

    def reset(self) -> None:
        """Resets all tracking states."""
        self._trackers.clear()
        self.total_candidates_processed = 0
        self.total_transient_suppressed = 0
        self.total_confirmed_emitted = 0
