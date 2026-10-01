"""
AlertEvent Pydantic Contract Model.
Directly maps to alert-event.schema.json (Draft 2020-12).
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict

from agri_telemetry.domain.enums import (
    AlertCategory,
    AlertSeverity,
    ThresholdType,
)


class TriggerCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold_type: ThresholdType
    threshold_value: float
    threshold_unit: Optional[str] = None
    forecast_horizon_hours: Optional[int] = None
    exceedance_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    predicted_value: Optional[float] = None


class AlertContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop_type: Optional[str] = None
    growth_stage: Optional[str] = None
    current_depletion_fraction: Optional[float] = None
    forecast_model_id: Optional[str] = None
    qc_failure_reason: Optional[str] = None


class AlertEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0", pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    alert_id: str
    category: AlertCategory
    severity: AlertSeverity
    source_id: str = Field(..., min_length=1)
    site_id: str = Field(..., min_length=1)
    trigger_time: str
    trigger_condition: TriggerCondition
    context: Optional[AlertContext] = None
    actionable_guidance: str = Field(..., min_length=5)
    is_autonomous_actuation: Literal[False] = Field(default=False)

    @field_validator("alert_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"alert_id must be a valid UUID string, got '{v}'")

    @field_validator("trigger_time")
    @classmethod
    def validate_trigger_time(cls, v: str) -> str:
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt.isoformat().replace("+00:00", "Z")
        except Exception as e:
            raise ValueError(f"Invalid ISO 8601 UTC timestamp for trigger_time: '{v}': {e}")

    @classmethod
    def create_new(
        cls,
        category: AlertCategory,
        severity: AlertSeverity,
        source_id: str,
        site_id: str,
        trigger_time: datetime,
        trigger_condition: TriggerCondition,
        actionable_guidance: str,
        context: Optional[AlertContext] = None,
    ) -> "AlertEvent":
        """Factory method to construct a validated AlertEvent."""
        a_id = str(uuid4())
        return cls(
            schema_version="1.0.0",
            alert_id=a_id,
            category=category,
            severity=severity,
            source_id=source_id,
            site_id=site_id,
            trigger_time=trigger_time.isoformat().replace("+00:00", "Z") if trigger_time.tzinfo else f"{trigger_time.isoformat()}Z",
            trigger_condition=trigger_condition,
            context=context,
            actionable_guidance=actionable_guidance,
            is_autonomous_actuation=False,
        )

    def to_dict(self) -> dict:
        """Serializes model to dictionary strictly matching Draft 2020-12 schema."""
        data = self.model_dump(mode="json")
        if data.get("context") is None:
            data.pop("context", None)
        else:
            data["context"] = {k: v for k, v in data["context"].items() if v is not None}
            if not data["context"]:
                data.pop("context", None)

        tc = data.get("trigger_condition", {})
        data["trigger_condition"] = {k: v for k, v in tc.items() if v is not None}
        return data

    def to_json(self) -> str:
        """Serializes model to JSON string matching Draft 2020-12 schema."""
        import json
        return json.dumps(self.to_dict())



