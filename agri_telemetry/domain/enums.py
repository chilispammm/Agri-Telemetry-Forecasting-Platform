"""
Domain Enums for Agri Telemetry & Forecasting Platform.
Strictly maps to JSON Schema Draft 2020-12 specifications.
"""

from enum import Enum


class DataClass(str, Enum):
    OBSERVED = "OBSERVED"
    MODELLED_REANALYSIS = "MODELLED_REANALYSIS"
    SIMULATED_REPLAY = "SIMULATED_REPLAY"
    SYNTHETIC_FAULT = "SYNTHETIC_FAULT"


class SyntheticFaultType(str, Enum):
    VALUE_SPIKE = "VALUE_SPIKE"
    SENSOR_STUCK = "SENSOR_STUCK"
    CLOCK_DRIFT = "CLOCK_DRIFT"
    PACKET_DROP = "PACKET_DROP"
    NON_PHYSICAL_RANGE = "NON_PHYSICAL_RANGE"


class VariableName(str, Enum):
    VOLUMETRIC_WATER_CONTENT = "volumetric_water_content"
    SOIL_TEMPERATURE = "soil_temperature"
    AIR_TEMPERATURE = "air_temperature"
    RELATIVE_HUMIDITY = "relative_humidity"
    PRECIPITATION = "precipitation"
    SOLAR_RADIATION = "solar_radiation"
    WIND_SPEED = "wind_speed"
    ATMOSPHERIC_PRESSURE = "atmospheric_pressure"
    VAPOR_PRESSURE_DEFICIT = "vapor_pressure_deficit"


class Unit(str, Enum):
    M3_M3 = "m3/m3"
    DEGC = "degC"
    MM = "mm"
    W_M2 = "W/m2"
    M_S = "m/s"
    KPA = "kPa"
    PERCENT = "percent"
    FRACTION = "fraction"


class QCFlag(str, Enum):
    VALID = "VALID"
    SUSPECT_SPIKE = "SUSPECT_SPIKE"
    SUSPECT_STUCK = "SUSPECT_STUCK"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    MISSING = "MISSING"
    SYNTHETIC_CORRUPTED = "SYNTHETIC_CORRUPTED"


class TargetVariable(str, Enum):
    VOLUMETRIC_WATER_CONTENT = "volumetric_water_content"
    ROOT_ZONE_DEPLETION_FRACTION = "root_zone_depletion_fraction"
    FRACTION_OF_AVAILABLE_WATER = "fraction_of_available_water"
    ROOT_ZONE_STORAGE_MM = "root_zone_storage_mm"


class AlertCategory(str, Enum):
    DATA_QUALITY_ALERT = "DATA_QUALITY_ALERT"
    PHYSICAL_DEVIATION = "PHYSICAL_DEVIATION"
    AGRONOMIC_RISK = "AGRONOMIC_RISK"
    OPERATIONAL_WARNING = "OPERATIONAL_WARNING"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ThresholdType(str, Enum):
    SENSOR_OUT_OF_RANGE = "SENSOR_OUT_OF_RANGE"
    SENSOR_STUCK_VALUE = "SENSOR_STUCK_VALUE"
    TELEMETRY_LATENCY_BREACH = "TELEMETRY_LATENCY_BREACH"
    MASS_BALANCE_RESIDUAL = "MASS_BALANCE_RESIDUAL"
    MANAGEMENT_ALLOWABLE_DEPLETION = "MANAGEMENT_ALLOWABLE_DEPLETION"
    CRITICAL_WILTING_PROXIMITY = "CRITICAL_WILTING_PROXIMITY"
