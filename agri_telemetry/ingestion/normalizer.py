"""
Telemetry Event Normalizer.
Converts parsed USCRN hourly station records into canonical TelemetryEvent domain objects.
"""

from datetime import datetime, timezone
from typing import List, Optional
import pandas as pd

from agri_telemetry.contracts.telemetry_event import (
    TelemetryEvent,
    TelemetryMeasurement,
)
from agri_telemetry.domain.enums import (
    DataClass,
    VariableName,
    Unit,
    QCFlag,
)


def normalize_uscrn_dataframe(
    df: pd.DataFrame,
    source_id: str,
    site_id: str,
    data_class: DataClass = DataClass.OBSERVED,
    dataset_version: str = "CRNH0203",
    ingest_time: Optional[datetime] = None,
) -> List[TelemetryEvent]:
    """
    Transforms a parsed USCRN pandas DataFrame into a stream of validated TelemetryEvents.
    """
    events: List[TelemetryEvent] = []

    for _, row in df.iterrows():
        dt_utc: datetime = row["timestamp_utc"]
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)

        measurements: List[TelemetryMeasurement] = []

        # Soil Moisture depths
        sm_depths = [
            ("soil_moisture_5cm", 5.0),
            ("soil_moisture_10cm", 10.0),
            ("soil_moisture_20cm", 20.0),
            ("soil_moisture_50cm", 50.0),
            ("soil_moisture_100cm", 100.0),
        ]
        for col, depth in sm_depths:
            val = row.get(col)
            qc = QCFlag.MISSING if (val is None or pd.isna(val)) else QCFlag.VALID
            measurements.append(
                TelemetryMeasurement(
                    sensor_id=f"SOIL_VWC_{int(depth)}CM",
                    variable_name=VariableName.VOLUMETRIC_WATER_CONTENT,
                    depth_cm=depth,
                    value=float(val) if qc == QCFlag.VALID else None,
                    unit=Unit.M3_M3,
                    qc_flag=qc,
                )
            )

        # Soil Temperature depths
        st_depths = [
            ("soil_temp_5cm", 5.0),
            ("soil_temp_10cm", 10.0),
            ("soil_temp_20cm", 20.0),
            ("soil_temp_50cm", 50.0),
            ("soil_temp_100cm", 100.0),
        ]
        for col, depth in st_depths:
            val = row.get(col)
            qc = QCFlag.MISSING if (val is None or pd.isna(val)) else QCFlag.VALID
            measurements.append(
                TelemetryMeasurement(
                    sensor_id=f"SOIL_TEMP_{int(depth)}CM",
                    variable_name=VariableName.SOIL_TEMPERATURE,
                    depth_cm=depth,
                    value=float(val) if qc == QCFlag.VALID else None,
                    unit=Unit.DEGC,
                    qc_flag=qc,
                )
            )

        # Air Temperature
        air_t = row.get("air_temp_c") or row.get("air_temp_hr_avg_c")
        qc_air = QCFlag.MISSING if (air_t is None or pd.isna(air_t)) else QCFlag.VALID
        measurements.append(
            TelemetryMeasurement(
                sensor_id="MET_AIR_TEMP_150CM",
                variable_name=VariableName.AIR_TEMPERATURE,
                depth_cm=0.0,
                value=float(air_t) if qc_air == QCFlag.VALID else None,
                unit=Unit.DEGC,
                qc_flag=qc_air,
            )
        )

        # Precipitation
        p_val = row.get("precip_mm")
        qc_p = QCFlag.MISSING if (p_val is None or pd.isna(p_val)) else QCFlag.VALID
        measurements.append(
            TelemetryMeasurement(
                sensor_id="MET_PRECIP_GAUGE",
                variable_name=VariableName.PRECIPITATION,
                depth_cm=0.0,
                value=float(p_val) if qc_p == QCFlag.VALID else None,
                unit=Unit.MM,
                qc_flag=qc_p,
            )
        )

        # Solar Radiation
        sol_val = row.get("solar_rad_wm2")
        qc_sol = QCFlag.MISSING if (sol_val is None or pd.isna(sol_val)) else QCFlag.VALID
        measurements.append(
            TelemetryMeasurement(
                sensor_id="MET_SOLAR_RAD",
                variable_name=VariableName.SOLAR_RADIATION,
                depth_cm=0.0,
                value=float(sol_val) if qc_sol == QCFlag.VALID else None,
                unit=Unit.W_M2,
                qc_flag=qc_sol,
            )
        )

        # Relative Humidity
        rh_val = row.get("rh_percent")
        qc_rh = QCFlag.MISSING if (rh_val is None or pd.isna(rh_val)) else QCFlag.VALID
        measurements.append(
            TelemetryMeasurement(
                sensor_id="MET_REL_HUMIDITY",
                variable_name=VariableName.RELATIVE_HUMIDITY,
                depth_cm=0.0,
                value=float(rh_val) if qc_rh == QCFlag.VALID else None,
                unit=Unit.PERCENT,
                qc_flag=qc_rh,
            )
        )

        event = TelemetryEvent.create_new(
            source_id=source_id,
            site_id=site_id,
            event_time=dt_utc,
            measurements=measurements,
            data_class=data_class,
            network="USCRN",
            dataset_version=dataset_version,
            ingest_time=ingest_time,
        )
        events.append(event)

    return events
