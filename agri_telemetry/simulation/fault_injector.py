"""
Synthetic Fault Injector.
Injects labelled faults into TelemetryEvents for quality control and quarantine verification.
"""

from dataclasses import dataclass
from typing import List, Optional
from uuid import uuid4

from agri_telemetry.contracts.telemetry_event import (
    TelemetryEvent,
    TelemetryMeasurement,
    TelemetryProvenance,
    QCSummary,
)
from agri_telemetry.domain.enums import (
    DataClass,
    SyntheticFaultType,
    VariableName,
    QCFlag,
)


@dataclass
class FaultSpec:
    target_index: int
    sensor_id: str
    fault_type: SyntheticFaultType
    corrupted_value: Optional[float] = None
    duration_steps: int = 1


def inject_synthetic_faults(
    events: List[TelemetryEvent],
    fault_specs: List[FaultSpec],
) -> List[TelemetryEvent]:
    """
    Applies synthetic faults to a sequence of TelemetryEvents, updating provenance and values.
    """
    output_events = list(events)

    for spec in fault_specs:
        start_idx = spec.target_index
        end_idx = min(len(events), start_idx + spec.duration_steps)

        for i in range(start_idx, end_idx):
            original = output_events[i]
            updated_measurements: List[TelemetryMeasurement] = []

            for m in original.measurements:
                if m.sensor_id == spec.sensor_id:
                    # Determine corrupted value
                    if spec.fault_type == SyntheticFaultType.NON_PHYSICAL_RANGE:
                        val = spec.corrupted_value if spec.corrupted_value is not None else 1.85
                    elif spec.fault_type == SyntheticFaultType.VALUE_SPIKE:
                        base = m.value if m.value is not None else 0.25
                        val = spec.corrupted_value if spec.corrupted_value is not None else (base + 0.35)
                    elif spec.fault_type == SyntheticFaultType.SENSOR_STUCK:
                        # Value locked to first step's value or corrupted_value
                        val = spec.corrupted_value if spec.corrupted_value is not None else 0.2222
                    elif spec.fault_type == SyntheticFaultType.PACKET_DROP:
                        val = None
                    else:
                        val = spec.corrupted_value

                    updated_measurements.append(
                        TelemetryMeasurement(
                            sensor_id=m.sensor_id,
                            variable_name=m.variable_name,
                            depth_cm=m.depth_cm,
                            value=val,
                            unit=m.unit,
                            qc_flag=QCFlag.SYNTHETIC_CORRUPTED if val is not None else QCFlag.MISSING,
                        )
                    )
                else:
                    updated_measurements.append(m)

            corrupted_event = TelemetryEvent(
                schema_version=original.schema_version,
                event_id=str(uuid4()),
                source_id=original.source_id,
                site_id=original.site_id,
                event_time=original.event_time,
                ingest_time=original.ingest_time,
                provenance=TelemetryProvenance(
                    data_class=DataClass.SYNTHETIC_FAULT,
                    network=original.provenance.network,
                    dataset_version=original.provenance.dataset_version,
                    synthetic_fault_type=spec.fault_type,
                ),
                measurements=updated_measurements,
                qc_summary=QCSummary(
                    all_valid=False,
                    flag_count=1,
                    quarantined=True,
                ),
            )
            output_events[i] = corrupted_event

    return output_events
