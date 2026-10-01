"""
Tier-1 Quality Control Engine.
Processes TelemetryEvents, applies quality rules, and performs anomaly isolation.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from agri_telemetry.contracts.telemetry_event import (
    TelemetryEvent,
    TelemetryMeasurement,
    QCSummary,
)
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.domain.enums import VariableName, QCFlag
from agri_telemetry.qc.rules import (
    check_physical_range,
    check_vwc_spike,
    check_stuck_sensor,
)
from agri_telemetry.qc.quarantine import QuarantineBuffer


class Tier1QCEngine:
    """
    Tier-1 Quality Control Evaluation Engine.
    Tracks stateful sensor history and isolates corrupted records.
    """

    def __init__(
        self,
        quarantine_buffer: Optional[QuarantineBuffer] = None,
        stuck_window_hours: int = 12,
        max_vwc_dry_delta: float = 0.15,
    ):
        self.quarantine_buffer = quarantine_buffer or QuarantineBuffer()
        self.stuck_window_hours = stuck_window_hours
        self.max_vwc_dry_delta = max_vwc_dry_delta

        # Sliding sensor history: {sensor_id: [recent values]}
        self._sensor_history: Dict[str, List[Optional[float]]] = defaultdict(list)
        # Last known precipitation
        self._last_precip_mm: Optional[float] = 0.0

    def evaluate_event(self, event: TelemetryEvent) -> Tuple[TelemetryEvent, bool, Optional[AlertEvent]]:
        """
        Applies Tier-1 QC rules to all measurements in a TelemetryEvent.
        Returns: (evaluated_event, is_quarantined, data_quality_alert)
        """
        # First extract collocated precipitation if present
        for m in event.measurements:
            if m.variable_name == VariableName.PRECIPITATION and m.value is not None:
                self._last_precip_mm = m.value

        updated_measurements: List[TelemetryMeasurement] = []
        failure_reasons: List[str] = []

        for m in event.measurements:
            current_qc = m.qc_flag

            # If already explicitly flagged as synthetic corruption, preserve
            if current_qc == QCFlag.SYNTHETIC_CORRUPTED:
                failure_reasons.append(f"Synthetic corruption injected on {m.sensor_id}")
                updated_measurements.append(m)
                continue

            # 1. Physical Range Check
            range_flag = check_physical_range(m.variable_name, m.value)
            if range_flag != QCFlag.VALID:
                current_qc = range_flag
                if range_flag == QCFlag.OUT_OF_RANGE:
                    failure_reasons.append(f"Physical range breach on {m.sensor_id} (value={m.value} {m.unit.value})")

            # 2. Stateful Soil VWC Spike Check
            if (
                current_qc == QCFlag.VALID
                and m.variable_name == VariableName.VOLUMETRIC_WATER_CONTENT
                and m.value is not None
            ):
                hist = self._sensor_history[m.sensor_id]
                prev_val = hist[-1] if hist else None
                spike_flag = check_vwc_spike(
                    current_vwc=m.value,
                    prev_vwc=prev_val,
                    precipitation_mm=self._last_precip_mm,
                    max_dry_delta=self.max_vwc_dry_delta,
                )
                if spike_flag != QCFlag.VALID:
                    current_qc = spike_flag
                    failure_reasons.append(f"Rate-of-change spike on {m.sensor_id} (|delta| > {self.max_vwc_dry_delta})")

            # 3. Stuck Sensor Flatline Check
            if current_qc == QCFlag.VALID and m.value is not None:
                hist = self._sensor_history[m.sensor_id]
                recent_window = hist + [m.value]
                stuck_flag = check_stuck_sensor(
                    recent_window,
                    variable=m.variable_name,
                    depth_cm=m.depth_cm,
                    min_stuck_hours=self.stuck_window_hours,
                )
                if stuck_flag != QCFlag.VALID:
                    current_qc = stuck_flag
                    failure_reasons.append(f"Sensor stuck/flatline on {m.sensor_id} for >= {self.stuck_window_hours} hours")


            # Update rolling history (limit to stuck_window_hours + 5)
            self._sensor_history[m.sensor_id].append(m.value)
            if len(self._sensor_history[m.sensor_id]) > (self.stuck_window_hours + 10):
                self._sensor_history[m.sensor_id].pop(0)

            updated_measurements.append(
                TelemetryMeasurement(
                    sensor_id=m.sensor_id,
                    variable_name=m.variable_name,
                    depth_cm=m.depth_cm,
                    value=m.value,
                    unit=m.unit,
                    qc_flag=current_qc,
                )
            )

        # Calculate updated QC summary
        flag_count = sum(1 for m in updated_measurements if m.qc_flag != QCFlag.VALID)
        is_quarantined = any(
            m.qc_flag in (QCFlag.OUT_OF_RANGE, QCFlag.SUSPECT_SPIKE, QCFlag.SUSPECT_STUCK, QCFlag.SYNTHETIC_CORRUPTED)
            for m in updated_measurements
        )

        qc_summary = QCSummary(
            all_valid=(flag_count == 0),
            flag_count=flag_count,
            quarantined=is_quarantined,
        )

        # Construct updated event
        evaluated_event = TelemetryEvent(
            schema_version=event.schema_version,
            event_id=event.event_id,
            source_id=event.source_id,
            site_id=event.site_id,
            event_time=event.event_time,
            ingest_time=event.ingest_time,
            provenance=event.provenance,
            measurements=updated_measurements,
            qc_summary=qc_summary,
        )

        # Handle quarantine routing and alert emission
        alert: Optional[AlertEvent] = None
        if is_quarantined:
            reason_str = "; ".join(failure_reasons) if failure_reasons else "Tier-1 QC fault detected"
            alert = self.quarantine_buffer.quarantine_event(evaluated_event, reason=reason_str)

        return evaluated_event, is_quarantined, alert

    def reset(self) -> None:
        """Resets internal history state."""
        self._sensor_history.clear()
        self._last_precip_mm = 0.0
