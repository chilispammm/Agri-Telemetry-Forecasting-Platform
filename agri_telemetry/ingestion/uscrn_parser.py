"""
USCRN Hourly Data Parser.
Parses fixed-width/space-separated NOAA CRNH0203 station files into structured records.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import numpy as np
import pandas as pd


# NOAA missing value sentinels
MISSING_SENTINELS = {-9999.0, -99.0, -99.000, -9999.00, -99999.0, -99.00, -9999, -99}

# Column names matching USCRN CRNH0203 hourly specification
USCRN_COLUMNS = [
    "WBANNO",
    "UTC_DATE",
    "UTC_TIME",
    "LST_DATE",
    "LST_TIME",
    "CRX_VN",
    "LONGITUDE",
    "LATITUDE",
    "T_CALC",
    "T_HR_AVG",
    "T_MAX",
    "T_MIN",
    "P_CALC",
    "SOLARAD",
    "SOLARAD_FLAG",
    "SOLARAD_MAX",
    "SOLARAD_MAX_FLAG",
    "SOLARAD_MIN",
    "SOLARAD_MIN_FLAG",
    "SUR_TEMP_TYPE",
    "SUR_TEMP",
    "SUR_TEMP_FLAG",
    "SUR_TEMP_MAX",
    "SUR_TEMP_MAX_FLAG",
    "SUR_TEMP_MIN",
    "SUR_TEMP_MIN_FLAG",
    "RH_HR_AVG",
    "RH_HR_AVG_FLAG",
    "SOIL_MOISTURE_5",
    "SOIL_MOISTURE_10",
    "SOIL_MOISTURE_20",
    "SOIL_MOISTURE_50",
    "SOIL_MOISTURE_100",
    "SOIL_TEMP_5",
    "SOIL_TEMP_10",
    "SOIL_TEMP_20",
    "SOIL_TEMP_50",
    "SOIL_TEMP_100",
]


def clean_missing_val(val: Any) -> Optional[float]:
    """Converts NOAA missing sentinels to None / NaN."""
    if val is None:
        return None
    try:
        fval = float(val)
        if fval in MISSING_SENTINELS or np.isnan(fval):
            return None
        return fval
    except (ValueError, TypeError):
        return None


def parse_uscrn_file(file_path: Union[str, Path]) -> pd.DataFrame:
    """
    Parses a USCRN CRNH0203 text file into a clean pandas DataFrame with UTC DatetimeIndex.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"USCRN data file not found: {path.resolve()}")

    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 38:
                continue

            # Parse UTC timestamp
            utc_date_str = parts[1]  # YYYYMMDD
            utc_time_str = parts[2]  # HHmm
            try:
                year = int(utc_date_str[0:4])
                month = int(utc_date_str[4:6])
                day = int(utc_date_str[6:8])
                hour = int(utc_time_str[0:2])
                minute = int(utc_time_str[2:4])
                
                # In USCRN, 2400 represents midnight of next day
                if hour == 24 and minute == 0:
                    dt_utc = datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc) + pd.Timedelta(days=1)
                else:
                    dt_utc = datetime(year, month, day, hour, minute, 0, tzinfo=timezone.utc)
            except Exception as e:
                raise ValueError(f"Failed parsing UTC date/time on line {line_num}: '{utc_date_str} {utc_time_str}': {e}")

            row: Dict[str, Any] = {
                "timestamp_utc": dt_utc,
                "station_wbanno": parts[0],
                "crx_version": parts[5],
                "longitude": float(parts[6]),
                "latitude": float(parts[7]),
                "air_temp_c": clean_missing_val(parts[8]),
                "air_temp_hr_avg_c": clean_missing_val(parts[9]),
                "precip_mm": clean_missing_val(parts[12]),
                "solar_rad_wm2": clean_missing_val(parts[13]),
                "solar_rad_flag": int(parts[14]),
                "sur_temp_c": clean_missing_val(parts[20]),
                "sur_temp_flag": int(parts[21]),
                "rh_percent": clean_missing_val(parts[26]),
                "rh_flag": int(parts[27]),
                "soil_moisture_5cm": clean_missing_val(parts[28]),
                "soil_moisture_10cm": clean_missing_val(parts[29]),
                "soil_moisture_20cm": clean_missing_val(parts[30]),
                "soil_moisture_50cm": clean_missing_val(parts[31]),
                "soil_moisture_100cm": clean_missing_val(parts[32]),
                "soil_temp_5cm": clean_missing_val(parts[33]),
                "soil_temp_10cm": clean_missing_val(parts[34]),
                "soil_temp_20cm": clean_missing_val(parts[35]),
                "soil_temp_50cm": clean_missing_val(parts[36]),
                "soil_temp_100cm": clean_missing_val(parts[37]),
            }
            records.append(row)

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
    return df
