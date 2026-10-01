"""
QC Quarantine and Dead-Letter Queue.
Isolates corrupted/suspect telemetry events and emits Tier-1 DATA_QUALITY_ALERTs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

from agri_telemetry.contracts.telemetry_event import TelemetryEvent, TelemetryMeasurement
from agri_telemetry.contracts.alert_event import (
    AlertEvent,
    TriggerCondition,
    AlertContext,
)
from agri_telemetry.domain.enums import (
    AlertCategory,
    AlertSeverity,
    ThresholdType,
    QCFlag,
)


@dataclass
class QuarantineRecord:
    event_id: str
    source_id: str
    site_id: str
    event_time: str
    quarantined_at: datetime
    reason: str
    failed_measurements: List[TelemetryMeasurement]
    original_event: TelemetryEvent


class QuarantineBuffer:
    """In-memory Dead-Letter Queue holding quarantined telemetry events."""

    def __init__(self):
        self._records: List[QuarantineRecord] = []
        self._alerts: List[AlertEvent] = []

    def quarantine_event(self, event: TelemetryEvent, reason: str) -> AlertEvent:
        """Quarantines a corrupt event and constructs a non-actuating DATA_QUALITY_ALERT."""
        failed = [
            m for m in event.measurements
            if m.qc_flag in (QCFlag.OUT_OF_RANGE, QCFlag.SUSPECT_SPIKE, QCFlag.SUSPECT_STUCK, QCFlag.SYNTHETIC_CORRUPTED)
        ]
        
        record = QuarantineRecord(
            event_id=event.event_id,
            source_id=event.source_id,
            site_id=event.site_id,
            event_time=event.event_time,
            quarantined_at=datetime.utcnow(),
            reason=reason,
            failed_measurements=failed,
            original_event=event,
        )
        self._records.append(record)

        # Map to specific threshold type
        thresh_type = ThresholdType.SENSOR_OUT_OF_RANGE
        for m in failed:
            if m.qc_flag == QCFlag.SUSPECT_STUCK:
                thresh_type = ThresholdType.SENSOR_STUCK_VALUE
                break

        trigger_val = failed[0].value if (failed and failed[0].value is not None) else 0.0
        trigger_unit = failed[0].unit.value if failed else "unitless"

        alert = AlertEvent.create_new(
            category=AlertCategory.DATA_QUALITY_ALERT,
            severity=AlertSeverity.CRITICAL,
            source_id=event.source_id,
            site_id=event.site_id,
            trigger_time=datetime.fromisoformat(event.event_time.replace("Z", "+00:00")),
            trigger_condition=TriggerCondition(
                threshold_type=thresh_type,
                threshold_value=float(trigger_val),
                threshold_unit=trigger_unit,
                predicted_value=float(trigger_val),
            ),
            context=AlertContext(
                qc_failure_reason=reason,
            ),
            actionable_guidance=(
                f"Data quality alert: Sensor observation quarantined due to {reason}. "
                "Downstream agronomic risk evaluation is isolated from this payload."
            ),
        )
        self._alerts.append(alert)
        return alert

    @property
    def records(self) -> List[QuarantineRecord]:
        return list(self._records)

    @property
    def alerts(self) -> List[AlertEvent]:
        return list(self._alerts)

    def count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        self._records.clear()
        self._alerts.clear()
