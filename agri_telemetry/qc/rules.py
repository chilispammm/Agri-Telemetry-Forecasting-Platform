"""
Tier-1 Quality Control Rules.
Physical range bounds, spike/rate-of-change filters, and flatline detection.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Tuple
from agri_telemetry.domain.enums import VariableName, QCFlag


# Physical range boundaries (min, max) per variable
PHYSICAL_RANGES: Dict[VariableName, Tuple[float, float]] = {
    VariableName.VOLUMETRIC_WATER_CONTENT: (0.00, 0.60),  # m3/m3
    VariableName.SOIL_TEMPERATURE: (-30.0, 60.0),          # degC
    VariableName.AIR_TEMPERATURE: (-50.0, 60.0),           # degC
    VariableName.PRECIPITATION: (0.0, 300.0),              # mm/hr
    VariableName.SOLAR_RADIATION: (0.0, 1500.0),           # W/m2
    VariableName.RELATIVE_HUMIDITY: (0.0, 100.0),          # percent
    VariableName.ATMOSPHERIC_PRESSURE: (50.0, 115.0),      # kPa
    VariableName.WIND_SPEED: (0.0, 75.0),                  # m/s
    VariableName.VAPOR_PRESSURE_DEFICIT: (0.0, 10.0),      # kPa
}


def check_physical_range(variable: VariableName, value: Optional[float]) -> QCFlag:
    """Evaluates whether a value falls within plausible physical limits."""
    if value is None:
        return QCFlag.MISSING

    bounds = PHYSICAL_RANGES.get(variable)
    if not bounds:
        return QCFlag.VALID

    min_val, max_val = bounds
    if value < min_val or value > max_val:
        return QCFlag.OUT_OF_RANGE
    return QCFlag.VALID


def check_vwc_spike(
    current_vwc: Optional[float],
    prev_vwc: Optional[float],
    precipitation_mm: Optional[float] = 0.0,
    max_dry_delta: float = 0.15,
) -> QCFlag:
    """
    Checks for impossible instantaneous step changes in soil moisture.
    If |vwc_t - vwc_{t-1}| > 0.15 m3/m3/hr without precipitation (P <= 0.2mm), flag as SUSPECT_SPIKE.
    """
    if current_vwc is None or prev_vwc is None:
        return QCFlag.VALID

    delta = abs(current_vwc - prev_vwc)
    has_precip = precipitation_mm is not None and precipitation_mm > 0.2

    if delta > max_dry_delta and not has_precip:
        return QCFlag.SUSPECT_SPIKE

    return QCFlag.VALID


def check_stuck_sensor(
    history: list,
    variable: Optional[VariableName] = None,
    depth_cm: float = 0.0,
    min_stuck_hours: int = 12,
    tolerance: float = 1e-5,
) -> QCFlag:
    """
    Checks if an active dynamic sensor channel has emitted the exact identical value for >= min_stuck_hours.
    Zero precipitation or nighttime solar radiation are natural and excluded from stuck checks.
    Deep soil layers (> 20cm) have strong physical inertia and are exempted for short hourly windows.
    """
    if len(history) < min_stuck_hours:
        return QCFlag.VALID

    valid_vals = [v for v in history[-min_stuck_hours:] if v is not None]
    if len(valid_vals) < min_stuck_hours:
        return QCFlag.VALID

    first_val = valid_vals[0]

    # Exempt natural zero states
    if variable == VariableName.PRECIPITATION and first_val == 0.0:
        return QCFlag.VALID
    if variable == VariableName.SOLAR_RADIATION and first_val == 0.0:
        return QCFlag.VALID

    # Deep soil sensors have high physical inertia
    if depth_cm >= 20.0 and min_stuck_hours < 48:
        return QCFlag.VALID

    if all(abs(v - first_val) <= tolerance for v in valid_vals):
        return QCFlag.SUSPECT_STUCK

    return QCFlag.VALID

