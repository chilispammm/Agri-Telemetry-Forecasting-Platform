"""
Operational & Scientific Configuration Management for Agri Telemetry & Forecasting Platform.
Separates scientific domain configuration from operational deployment configuration and secrets.
"""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
import yaml


@dataclass
class SoilConfig:
    """Scientific soil hydraulic profile parameters."""
    theta_fc: float = 0.33
    theta_wp: float = 0.13
    theta_sat: float = 0.45
    root_zone_depth_cm: float = 100.0
    layer_depths_cm: List[int] = field(default_factory=lambda: [5, 10, 20, 50, 100])
    layer_weights: List[float] = field(default_factory=lambda: [0.075, 0.075, 0.20, 0.35, 0.30])


@dataclass
class RiskConfig:
    """Scientific agronomic water deficit threshold parameters."""
    d_mad: float = 0.50
    d_wilt: float = 0.85
    tau_risk: float = 0.70
    action_horizon_hours: int = 24


@dataclass
class ForecastingConfig:
    """Forecasting horizons, model routing, and uncertainty settings."""
    horizons: List[int] = field(default_factory=lambda: [1, 6, 12, 24, 48, 72, 168])
    target_variable: str = "volumetric_water_content"
    model_strategy: str = "HORIZON_PARTITIONED"  # M2 (1-48h), M1 (72-168h)
    uncertainty_method: str = "REGIME_CONDITIONED"  # U2 dynamic scaling
    random_seed: int = 42


@dataclass
class StreamingConfig:
    """Operational event-stream broker settings."""
    broker_type: str = "IN_MEMORY"  # "IN_MEMORY" or "REDIS"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    telemetry_stream: str = "stream:telemetry"
    forecast_stream: str = "stream:forecasts"
    alert_stream: str = "stream:alerts"
    consumer_group: str = "agri_workers"
    batch_size: int = 100


@dataclass
class ObservabilityConfig:
    """Operational structured logging and metrics settings."""
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"
    service_name: str = "agri-telemetry-platform"
    environment: str = "development"
    enable_metrics: bool = True
    metrics_port: int = 9090


@dataclass
class StorageConfig:
    """Persistence and evidence storage paths."""
    db_path: str = "data/agri_telemetry.db"
    runs_dir: str = "runs"
    ledger_file: str = "runs/evidence_ledger.md"


@dataclass
class MLOpsConfig:
    """Experiment lifecycle and model tracking settings."""
    tracking_enabled: bool = True
    tracking_backend: str = "LOCAL_LEDGER"  # "LOCAL_LEDGER" or "MLFLOW"
    mlflow_tracking_uri: str = "file:./runs/mlruns"
    experiment_name: str = "agri-telemetry-forecasting"


@dataclass
class ReliabilityConfig:
    """Operational resilience and fault tolerance settings."""
    max_retries: int = 3
    retry_backoff_sec: float = 1.0
    dlq_enabled: bool = True
    fallback_to_persistence: bool = True
    persistence_filter_mode: str = "CONSECUTIVE_2"  # "CONSECUTIVE_2", "CONSECUTIVE_3", "N_OF_M_3_5"


@dataclass
class AppConfig:
    """Master Application Configuration."""
    station_id: str = "USCRN_NE_Lincoln_11_SW"
    site_id: str = "FIELD_LINCOLN_01"
    soil: SoilConfig = field(default_factory=SoilConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    forecasting: ForecastingConfig = field(default_factory=ForecastingConfig)
    streaming: StreamingConfig = field(default_factory=StreamingConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    mlops: MLOpsConfig = field(default_factory=MLOpsConfig)
    reliability: ReliabilityConfig = field(default_factory=ReliabilityConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "AppConfig":
        """Loads configuration from a YAML file, falling back to defaults for missing keys."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Configuration file not found: {p.resolve()}")
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        config = cls()
        if "station_id" in data:
            config.station_id = data["station_id"]
        if "site_id" in data:
            config.site_id = data["site_id"]
        if "soil" in data:
            config.soil = SoilConfig(**data["soil"])
        if "risk" in data:
            config.risk = RiskConfig(**data["risk"])
        if "forecasting" in data:
            config.forecasting = ForecastingConfig(**data["forecasting"])
        if "streaming" in data:
            config.streaming = StreamingConfig(**data["streaming"])
        if "observability" in data:
            config.observability = ObservabilityConfig(**data["observability"])
        if "storage" in data:
            config.storage = StorageConfig(**data["storage"])
        if "mlops" in data:
            config.mlops = MLOpsConfig(**data["mlops"])
        if "reliability" in data:
            config.reliability = ReliabilityConfig(**data["reliability"])
        return config

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Constructs configuration with environment variable overrides."""
        config = cls()
        if "AGRI_STATION_ID" in os.environ:
            config.station_id = os.environ["AGRI_STATION_ID"]
        if "AGRI_SITE_ID" in os.environ:
            config.site_id = os.environ["AGRI_SITE_ID"]
        if "AGRI_LOG_LEVEL" in os.environ:
            config.observability.log_level = os.environ["AGRI_LOG_LEVEL"]
        if "AGRI_LOG_FORMAT" in os.environ:
            config.observability.log_format = os.environ["AGRI_LOG_FORMAT"]
        if "AGRI_ENV" in os.environ:
            config.observability.environment = os.environ["AGRI_ENV"]
        if "AGRI_DB_PATH" in os.environ:
            config.storage.db_path = os.environ["AGRI_DB_PATH"]
        if "AGRI_RUNS_DIR" in os.environ:
            config.storage.runs_dir = os.environ["AGRI_RUNS_DIR"]
        if "AGRI_STREAM_BROKER" in os.environ:
            config.streaming.broker_type = os.environ["AGRI_STREAM_BROKER"]
        if "AGRI_REDIS_HOST" in os.environ:
            config.streaming.redis_host = os.environ["AGRI_REDIS_HOST"]
        if "AGRI_REDIS_PORT" in os.environ:
            config.streaming.redis_port = int(os.environ["AGRI_REDIS_PORT"])
        if "AGRI_MLOPS_BACKEND" in os.environ:
            config.mlops.tracking_backend = os.environ["AGRI_MLOPS_BACKEND"]
        if "AGRI_MLFLOW_URI" in os.environ:
            config.mlops.mlflow_tracking_uri = os.environ["AGRI_MLFLOW_URI"]
        return config

    def to_dict(self) -> Dict[str, Any]:
        """Converts configuration to nested dictionary."""
        return asdict(self)

    def save_yaml(self, path: str | Path) -> None:
        """Saves configuration to YAML file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_dict(), f, sort_keys=False)
