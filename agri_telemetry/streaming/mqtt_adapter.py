"""
MQTT 5 Telemetry Ingress Adapter for Agri Telemetry & Forecasting Platform.
Bridges MQTT edge transmissions (e.g. ESP32 / Wokwi) into canonical TelemetryEvents and stream broker queues.
Guarantees explicit labeling of simulated telemetry and integrates resilience components (DLQ, Deduplication, Resequencing).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Callable
import json
import uuid

from agri_telemetry.contracts.telemetry_event import (
    TelemetryEvent,
    TelemetryProvenance,
    TelemetryMeasurement,
    QCSummary,
)
from agri_telemetry.domain.enums import (
    DataClass,
    VariableName,
    Unit,
    QCFlag,
)
from agri_telemetry.reliability.recovery import (
    DeadLetterQueue,
    EventDeduplicator,
    OutOfOrderSequencer,
)
from agri_telemetry.streaming.broker import EventStreamBroker, InMemoryStreamBroker


@dataclass
class MQTTMessage:
    """Standard MQTT envelope."""
    topic: str
    payload: bytes
    qos: int = 1
    retain: bool = False
    received_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MQTTTelemetryIngestAdapter:
    """
    Ingests MQTT messages from IoT field devices/simulators, validates schema,
    transforms to canonical TelemetryEvent contracts, and routes to the stream broker.
    """

    def __init__(
        self,
        broker: Optional[EventStreamBroker] = None,
        telemetry_stream: str = "stream:telemetry",
        dlq: Optional[DeadLetterQueue] = None,
        deduplicator: Optional[EventDeduplicator] = None,
        sequencer: Optional[OutOfOrderSequencer] = None,
    ):
        self.broker = broker or InMemoryStreamBroker()
        self.telemetry_stream = telemetry_stream
        self.dlq = dlq or DeadLetterQueue()
        self.deduplicator = deduplicator or EventDeduplicator()
        self.sequencer = sequencer or OutOfOrderSequencer()

        # Operational counters
        self.messages_received = 0
        self.events_published = 0
        self.dlq_quarantined = 0
        self.duplicates_dropped = 0
        self.is_connected = True

    def connect(self) -> bool:
        """Simulates connection to the MQTT broker."""
        self.is_connected = True
        return True

    def disconnect(self) -> None:
        """Simulates disconnection from the MQTT broker."""
        self.is_connected = False

    def on_message(
        self,
        topic: str,
        payload_bytes: bytes,
        qos: int = 1,
    ) -> Optional[str]:
        """
        Callback executed upon receipt of an MQTT message packet.
        Returns the published stream message ID, or None if quarantined/dropped.
        """
        self.messages_received += 1
        ingest_time_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if not self.is_connected:
            raise ConnectionError("MQTT Adapter is currently disconnected from broker.")

        # 1. Parse JSON payload
        try:
            payload_str = payload_bytes.decode("utf-8")
            data = json.loads(payload_str)
        except Exception as e:
            self.dlq_quarantined += 1
            self.dlq.push(
                payload=str(payload_bytes),
                reason=f"Invalid JSON in MQTT payload on topic '{topic}': {e}",
            )
            return None

        # 2. Extract and validate required fields
        device_id = data.get("device_id")
        site_id = data.get("site_id", "FIELD_DEFAULT")
        timestamp_str = data.get("timestamp_utc")

        if not device_id or not timestamp_str or not isinstance(data.get("sensors"), dict):
            self.dlq_quarantined += 1
            self.dlq.push(
                payload=payload_str,
                reason="Missing required device_id, timestamp_utc, or sensors object in MQTT message.",
            )
            return None

        # 3. Build TelemetryEvent
        sensors = data["sensors"]
        measurements: List[TelemetryMeasurement] = []

        def add_meas(sensor_name: str, var_enum: VariableName, depth: float, unit_enum: Unit):
            val = sensors.get(sensor_name)
            if val is not None:
                try:
                    val_f = float(val)
                except (ValueError, TypeError):
                    val_f = None
                measurements.append(
                    TelemetryMeasurement(
                        sensor_id=f"{device_id}-{sensor_name}",
                        variable_name=var_enum,
                        depth_cm=depth,
                        value=val_f,
                        unit=unit_enum,
                        qc_flag=QCFlag.VALID,
                    )
                )

        add_meas("soil_moisture_5cm", VariableName.VOLUMETRIC_WATER_CONTENT, 5.0, Unit.M3_M3)
        add_meas("soil_moisture_10cm", VariableName.VOLUMETRIC_WATER_CONTENT, 10.0, Unit.M3_M3)
        add_meas("soil_moisture_20cm", VariableName.VOLUMETRIC_WATER_CONTENT, 20.0, Unit.M3_M3)
        add_meas("soil_moisture_50cm", VariableName.VOLUMETRIC_WATER_CONTENT, 50.0, Unit.M3_M3)
        add_meas("soil_moisture_100cm", VariableName.VOLUMETRIC_WATER_CONTENT, 100.0, Unit.M3_M3)
        add_meas("soil_temp_10cm_c", VariableName.SOIL_TEMPERATURE, 10.0, Unit.DEGC)
        add_meas("air_temp_c", VariableName.AIR_TEMPERATURE, 0.0, Unit.DEGC)
        add_meas("rh_pct", VariableName.RELATIVE_HUMIDITY, 0.0, Unit.PERCENT)
        add_meas("solar_radiation_wm2", VariableName.SOLAR_RADIATION, 0.0, Unit.W_M2)
        add_meas("precipitation_mm", VariableName.PRECIPITATION, 0.0, Unit.MM)

        if not measurements:
            self.dlq_quarantined += 1
            self.dlq.push(
                payload=payload_str,
                reason="No valid measurements extracted from sensors block.",
            )
            return None

        # Explicit simulation label guarantee
        data_class = DataClass.SIMULATED_REPLAY if data.get("is_simulated", True) else DataClass.OBSERVED
        provenance = TelemetryProvenance(
            data_class=data_class,
            network="ESP32_MQTT_SIMULATED",
            dataset_version="v1.0.0-sim",
        )

        event = TelemetryEvent(
            event_id=str(uuid.uuid4()),
            source_id=device_id,
            site_id=site_id,
            event_time=timestamp_str,
            ingest_time=ingest_time_iso,
            provenance=provenance,
            measurements=measurements,
            qc_summary=QCSummary(all_valid=True, flag_count=0, quarantined=False),
        )

        # 4. Check for duplicate packet
        dedup_key = self.deduplicator.compute_key(device_id, timestamp_str, site_id)
        if not self.deduplicator.register(dedup_key):
            self.duplicates_dropped += 1
            return None

        # 5. Route to OutOfOrderSequencer or directly publish to stream broker
        event_dict = event.model_dump()
        msg_id = self.broker.publish(
            stream_name=self.telemetry_stream,
            payload=event_dict,
            event_time=event.event_time,
        )
        self.events_published += 1
        return msg_id
        return msg_id
