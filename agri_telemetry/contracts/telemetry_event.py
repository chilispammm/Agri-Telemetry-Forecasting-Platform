"""
TelemetryEvent Pydantic Contract Model.
Directly maps to telemetry-event.schema.json (Draft 2020-12).
"""

import hashlib
from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict

from agri_telemetry.domain.enums import (
    DataClass,
    SyntheticFaultType,
    VariableName,
    Unit,
    QCFlag,
)


class TelemetryProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_class: DataClass
    network: str = Field(..., min_length=1)
    dataset_version: Optional[str] = None
    replay_session_id: Optional[str] = None
    synthetic_fault_type: Optional[SyntheticFaultType] = None


class TelemetryMeasurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensor_id: str = Field(..., min_length=1)
    variable_name: VariableName
    depth_cm: float = Field(..., ge=0.0)
    value: Optional[float]
    unit: Unit
    qc_flag: QCFlag = QCFlag.VALID


class QCSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all_valid: bool = True
    flag_count: int = Field(default=0, ge=0)
    quarantined: bool = False


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0", pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    event_id: str
    source_id: str = Field(..., min_length=1)
    site_id: str = Field(..., min_length=1)
    event_time: str  # ISO 8601 UTC
    ingest_time: str  # ISO 8601 UTC
    provenance: TelemetryProvenance
    measurements: List[TelemetryMeasurement] = Field(..., min_length=1)
    qc_summary: Optional[QCSummary] = None

    @field_validator("event_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"event_id must be a valid UUID string, got '{v}'")

    @field_validator("event_time", "ingest_time")
    @classmethod
    def validate_iso_timestamp(cls, v: str) -> str:
        try:
            # Parse to ensure valid ISO 8601 format
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt.isoformat().replace("+00:00", "Z")
        except Exception as e:
            raise ValueError(f"Invalid ISO 8601 UTC timestamp '{v}': {e}")

    @property
    def natural_key(self) -> str:
        """
        Computes the natural deduplication composite key:
        SHA256(source_id || event_time || data_class || schema_version)
        """
        key_raw = f"{self.source_id}|{self.event_time}|{self.provenance.data_class.value}|{self.schema_version}"
        return hashlib.sha256(key_raw.encode("utf-8")).hexdigest()

    @classmethod
    def create_new(
        cls,
        source_id: str,
        site_id: str,
        event_time: datetime,
        measurements: List[TelemetryMeasurement],
        data_class: DataClass = DataClass.OBSERVED,
        network: str = "USCRN",
        dataset_version: Optional[str] = None,
        synthetic_fault_type: Optional[SyntheticFaultType] = None,
        ingest_time: Optional[datetime] = None,
    ) -> "TelemetryEvent":
        """Factory method to construct a validated TelemetryEvent."""
        now_utc = ingest_time or datetime.utcnow()
        evt_id = str(uuid4())
        
        # Calculate QC summary
        flag_count = sum(1 for m in measurements if m.qc_flag != QCFlag.VALID)
        is_quarantined = any(
            m.qc_flag in [QCFlag.OUT_OF_RANGE, QCFlag.SUSPECT_SPIKE, QCFlag.SUSPECT_STUCK, QCFlag.SYNTHETIC_CORRUPTED]
            for m in measurements
        )
        
        return cls(
            schema_version="1.0.0",
            event_id=evt_id,
            source_id=source_id,
            site_id=site_id,
            event_time=event_time.isoformat().replace("+00:00", "Z") if event_time.tzinfo else f"{event_time.isoformat()}Z",
            ingest_time=now_utc.isoformat().replace("+00:00", "Z") if now_utc.tzinfo else f"{now_utc.isoformat()}Z",
            provenance=TelemetryProvenance(
                data_class=data_class,
                network=network,
                dataset_version=dataset_version,
                synthetic_fault_type=synthetic_fault_type,
            ),
            measurements=measurements,
            qc_summary=QCSummary(
                all_valid=(flag_count == 0),
                flag_count=flag_count,
                quarantined=is_quarantined,
            ),
        )

    def to_dict(self) -> dict:
        """Serializes model to dictionary strictly matching Draft 2020-12 schema."""
        data = self.model_dump(mode="json")
        if data.get("provenance", {}).get("dataset_version") is None:
            data["provenance"].pop("dataset_version", None)
        if data.get("provenance", {}).get("replay_session_id") is None:
            data["provenance"].pop("replay_session_id", None)
        if data.get("provenance", {}).get("synthetic_fault_type") is None:
            data["provenance"].pop("synthetic_fault_type", None)
        if data.get("qc_summary") is None:
            data.pop("qc_summary", None)
        return data

    def to_json(self) -> str:
        """Serializes model to JSON string matching Draft 2020-12 schema."""
        import json
        return json.dumps(self.to_dict())


