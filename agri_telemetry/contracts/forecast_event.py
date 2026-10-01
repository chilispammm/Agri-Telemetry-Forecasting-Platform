"""
ForecastEvent Pydantic Contract Model.
Directly maps to forecast-event.schema.json (Draft 2020-12).
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, ConfigDict

from agri_telemetry.domain.enums import TargetVariable, Unit


class FeatureLineage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1)
    variable: str = Field(..., min_length=1)
    lag_steps: Optional[List[int]] = None


class ModelMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str = Field(..., min_length=1)
    model_version: str = Field(..., min_length=1)
    training_cutoff_time: Optional[str] = None
    random_seed: Optional[int] = None
    feature_lineage: Optional[List[FeatureLineage]] = None

    @field_validator("training_cutoff_time")
    @classmethod
    def validate_training_cutoff(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt.isoformat().replace("+00:00", "Z")
        except Exception as e:
            raise ValueError(f"Invalid ISO 8601 UTC timestamp for training_cutoff_time: '{v}': {e}")


class Quantiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q10: Optional[float] = None
    q25: Optional[float] = None
    q50: Optional[float] = None
    q75: Optional[float] = None
    q90: Optional[float] = None


class PredictionInterval80(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lower: float
    upper: float


class HorizonPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    horizon_hours: int = Field(..., ge=1)
    valid_time: str
    point_forecast: float
    quantiles: Optional[Quantiles] = None
    prediction_interval_80: Optional[PredictionInterval80] = None
    unit: str = Field(..., pattern=r"^(m3/m3|fraction|mm|percent)$")

    @field_validator("valid_time")
    @classmethod
    def validate_valid_time(cls, v: str) -> str:
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt.isoformat().replace("+00:00", "Z")
        except Exception as e:
            raise ValueError(f"Invalid ISO 8601 UTC timestamp for valid_time: '{v}': {e}")


class ForecastEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0.0", pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    forecast_id: str
    source_id: str = Field(..., min_length=1)
    site_id: str = Field(..., min_length=1)
    forecast_origin_time: str
    generated_at: str
    target_variable: TargetVariable
    target_depth_range_cm: Optional[List[float]] = Field(default=None, min_length=2, max_length=2)
    model_metadata: ModelMetadata
    predictions: List[HorizonPrediction] = Field(..., min_length=1)

    @field_validator("forecast_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError(f"forecast_id must be a valid UUID string, got '{v}'")

    @field_validator("forecast_origin_time", "generated_at")
    @classmethod
    def validate_iso_timestamps(cls, v: str) -> str:
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt.isoformat().replace("+00:00", "Z")
        except Exception as e:
            raise ValueError(f"Invalid ISO 8601 UTC timestamp: '{v}': {e}")

    @classmethod
    def create_new(
        cls,
        source_id: str,
        site_id: str,
        forecast_origin_time: datetime,
        target_variable: TargetVariable,
        model_name: str,
        model_version: str,
        predictions: List[HorizonPrediction],
        target_depth_range_cm: Optional[List[float]] = None,
        training_cutoff_time: Optional[datetime] = None,
        random_seed: Optional[int] = None,
        feature_lineage: Optional[List[FeatureLineage]] = None,
        generated_at: Optional[datetime] = None,
    ) -> "ForecastEvent":
        """Factory method to construct a validated ForecastEvent."""
        now_utc = generated_at or datetime.utcnow()
        f_id = str(uuid4())

        return cls(
            schema_version="1.0.0",
            forecast_id=f_id,
            source_id=source_id,
            site_id=site_id,
            forecast_origin_time=forecast_origin_time.isoformat().replace("+00:00", "Z") if forecast_origin_time.tzinfo else f"{forecast_origin_time.isoformat()}Z",
            generated_at=now_utc.isoformat().replace("+00:00", "Z") if now_utc.tzinfo else f"{now_utc.isoformat()}Z",
            target_variable=target_variable,
            target_depth_range_cm=target_depth_range_cm,
            model_metadata=ModelMetadata(
                model_name=model_name,
                model_version=model_version,
                training_cutoff_time=(
                    training_cutoff_time.isoformat().replace("+00:00", "Z")
                    if training_cutoff_time
                    else None
                ),
                random_seed=random_seed,
                feature_lineage=feature_lineage,
            ),
            predictions=predictions,
        )

    def to_dict(self) -> dict:
        """Serializes model to dictionary strictly matching Draft 2020-12 schema."""
        data = self.model_dump(mode="json")
        if data.get("target_depth_range_cm") is None:
            data.pop("target_depth_range_cm", None)
        if data.get("model_metadata", {}).get("training_cutoff_time") is None:
            data["model_metadata"].pop("training_cutoff_time", None)
        if data.get("model_metadata", {}).get("random_seed") is None:
            data["model_metadata"].pop("random_seed", None)
        if data.get("model_metadata", {}).get("feature_lineage") is None:
            data["model_metadata"].pop("feature_lineage", None)
        for p in data.get("predictions", []):
            if p.get("quantiles") is None:
                p.pop("quantiles", None)
            if p.get("prediction_interval_80") is None:
                p.pop("prediction_interval_80", None)
        return data

    def to_json(self) -> str:
        """Serializes model to JSON string matching Draft 2020-12 schema."""
        import json
        return json.dumps(self.to_dict())


