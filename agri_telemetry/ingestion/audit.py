"""
Historical Telemetry Data Audit.
Analyzes coverage, cadence, missingness, duplicate timestamps, value ranges, and anomalies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd


@dataclass
class VariableAuditStats:
    variable_name: str
    non_null_count: int
    null_count: int
    null_percentage: float
    min_value: Optional[float]
    max_value: Optional[float]
    mean_value: Optional[float]
    std_value: Optional[float]


@dataclass
class IngestionAuditReport:
    dataset_name: str
    station_id: str
    start_time: datetime
    end_time: datetime
    total_records: int
    expected_hourly_steps: int
    missing_hourly_steps: int
    duplicate_timestamps: int
    variable_stats: Dict[str, VariableAuditStats] = field(default_factory=dict)
    audit_timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "station_id": self.station_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_records": self.total_records,
            "expected_hourly_steps": self.expected_hourly_steps,
            "missing_hourly_steps": self.missing_hourly_steps,
            "duplicate_timestamps": self.duplicate_timestamps,
            "variable_stats": {
                k: {
                    "non_null_count": v.non_null_count,
                    "null_count": v.null_count,
                    "null_percentage": round(v.null_percentage, 2),
                    "min_value": round(v.min_value, 4) if v.min_value is not None else None,
                    "max_value": round(v.max_value, 4) if v.max_value is not None else None,
                    "mean_value": round(v.mean_value, 4) if v.mean_value is not None else None,
                    "std_value": round(v.std_value, 4) if v.std_value is not None else None,
                }
                for k, v in self.variable_stats.items()
            },
        }

    def to_markdown_summary(self) -> str:
        lines = [
            f"### Ingestion Audit Report: {self.dataset_name} ({self.station_id})",
            f"- **Observation Range**: `{self.start_time.isoformat()}` to `{self.end_time.isoformat()}`",
            f"- **Total Ingested Records**: `{self.total_records:,}`",
            f"- **Expected Hourly Steps**: `{self.expected_hourly_steps:,}`",
            f"- **Missing Cadence Steps**: `{self.missing_hourly_steps}` ({self.missing_hourly_steps / max(1, self.expected_hourly_steps) * 100:.2f}%)",
            f"- **Duplicate Timestamps**: `{self.duplicate_timestamps}`",
            "",
            "| Variable | Valid Records | Missing / Null | Null % | Min | Max | Mean ± Std |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for name, stats in sorted(self.variable_stats.items()):
            mean_std = f"{stats.mean_value:.2f} ± {stats.std_value:.2f}" if stats.mean_value is not None and stats.std_value is not None else "N/A"
            min_v = f"{stats.min_value:.3f}" if stats.min_value is not None else "N/A"
            max_v = f"{stats.max_value:.3f}" if stats.max_value is not None else "N/A"
            lines.append(
                f"| `{name}` | {stats.non_null_count:,} | {stats.null_count:,} | {stats.null_percentage:.1f}% | {min_v} | {max_v} | {mean_std} |"
            )
        return "\n".join(lines)


def audit_uscrn_dataframe(
    df: pd.DataFrame,
    dataset_name: str = "USCRN_CRNH0203_2023",
    station_id: str = "NE_Lincoln_11_SW",
) -> IngestionAuditReport:
    """Performs comprehensive data quality and cadence audit on a parsed USCRN DataFrame."""
    if df.empty:
        raise ValueError("Cannot audit an empty DataFrame.")

    df_sorted = df.sort_values("timestamp_utc").reset_index(drop=True)
    start_t: datetime = df_sorted["timestamp_utc"].iloc[0]
    end_t: datetime = df_sorted["timestamp_utc"].iloc[-1]

    # Expected hourly timestamps
    expected_range = pd.date_range(start=start_t, end=end_t, freq="1h")
    expected_steps = len(expected_range)
    total_records = len(df_sorted)

    # Duplicates check
    dup_count = int(df_sorted["timestamp_utc"].duplicated().sum())

    # Cadence missingness
    actual_timestamps = set(df_sorted["timestamp_utc"])
    missing_steps = sum(1 for ts in expected_range if ts not in actual_timestamps)

    # Variable audits
    numeric_cols = [
        "air_temp_c",
        "precip_mm",
        "solar_rad_wm2",
        "rh_percent",
        "soil_moisture_5cm",
        "soil_moisture_10cm",
        "soil_moisture_20cm",
        "soil_moisture_50cm",
        "soil_moisture_100cm",
        "soil_temp_5cm",
        "soil_temp_10cm",
        "soil_temp_20cm",
        "soil_temp_50cm",
        "soil_temp_100cm",
    ]

    var_stats: Dict[str, VariableAuditStats] = {}
    for col in numeric_cols:
        if col not in df_sorted.columns:
            continue
        series = df_sorted[col]
        non_null = int(series.notna().sum())
        null_c = int(series.isna().sum())
        null_pct = (null_c / total_records * 100.0) if total_records > 0 else 0.0

        if non_null > 0:
            min_v = float(series.min())
            max_v = float(series.max())
            mean_v = float(series.mean())
            std_v = float(series.std()) if non_null > 1 else 0.0
        else:
            min_v, max_v, mean_v, std_v = None, None, None, None

        var_stats[col] = VariableAuditStats(
            variable_name=col,
            non_null_count=non_null,
            null_count=null_c,
            null_percentage=null_pct,
            min_value=min_v,
            max_value=max_v,
            mean_value=mean_v,
            std_value=std_v,
        )

    return IngestionAuditReport(
        dataset_name=dataset_name,
        station_id=station_id,
        start_time=start_t,
        end_time=end_t,
        total_records=total_records,
        expected_hourly_steps=expected_steps,
        missing_hourly_steps=missing_steps,
        duplicate_timestamps=dup_count,
        variable_stats=var_stats,
    )
