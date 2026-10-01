"""
Internal Domain Models for Agri Telemetry & Forecasting Platform.
Decoupled internal data classes supporting processing pipelines.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass(frozen=True)
class SensorObservation:
    """Internal representation of a single physical channel reading."""
    sensor_id: str
    variable_name: str
    depth_cm: float
    value: Optional[float]
    unit: str
    qc_flag: str
    raw_flag: Optional[str] = None


@dataclass
class SoilWaterState:
    """Estimated physical and agronomic soil-water state at time t."""
    timestamp: datetime
    site_id: str
    source_id: str
    # Multi-depth observations: {depth_cm: vwc_value}
    depth_vwc: Dict[float, float]
    # Effective root-zone integrated VWC (m3/m3)
    theta_rz: float
    # Configured soil physical limits used
    theta_fc: float
    theta_wp: float
    theta_sat: float
    # Derived agronomic indicators
    depletion_fraction: float  # Dr in [0, 1+]
    available_water_fraction: float  # (theta_rz - theta_wp) / (theta_fc - theta_wp)
    # Storage in millimeters over root-zone depth
    root_depth_cm: float
    storage_mm: float
    deficit_mm: float
    # Quality summary
    is_valid: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ForecastHorizonPrediction:
    """Point and probabilistic prediction for a specific lead time horizon."""
    horizon_hours: int
    target_time: datetime
    point_forecast: float
    unit: str
    # Empirical residual quantiles
    q10: Optional[float] = None
    q25: Optional[float] = None
    q50: Optional[float] = None
    q75: Optional[float] = None
    q90: Optional[float] = None
    # Working prediction interval
    pi_lower_80: Optional[float] = None
    pi_upper_80: Optional[float] = None
    # Derived threshold crossing probabilities
    exceedance_probability_mad: Optional[float] = None


@dataclass
class RunSummary:
    """Immutable audit record for a reproducible end-to-end execution."""
    run_id: str
    executed_at: datetime
    dataset_name: str
    station_id: str
    start_time: datetime
    end_time: datetime
    total_records: int
    valid_events_count: int
    quarantined_events_count: int
    forecast_events_count: int
    alert_events_count: int
    persistence_mae: Dict[int, float]
    persistence_rmse: Dict[int, float]
    persistence_skill: Dict[int, float]
    interval_80_coverage: Dict[int, float]
    random_seed: int
    config: Dict[str, Any]
