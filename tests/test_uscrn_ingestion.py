"""
Unit & Integration Tests for USCRN Ingestion, Normalization, and Data Audit.
"""

from pathlib import Path
import pytest

from agri_telemetry.ingestion import (
    parse_uscrn_file,
    normalize_uscrn_dataframe,
    audit_uscrn_dataframe,
)
from agri_telemetry.contracts import assert_valid_payload
from agri_telemetry.domain.enums import DataClass


USCRN_SAMPLE_PATH = Path(__file__).parent.parent / "data" / "uscrn" / "CRNH0203-2023-NE_Lincoln_11_SW.txt"


def test_uscrn_parser_file_exists():
    assert USCRN_SAMPLE_PATH.exists(), f"USCRN sample file missing: {USCRN_SAMPLE_PATH}"


def test_uscrn_parser_load():
    df = parse_uscrn_file(USCRN_SAMPLE_PATH)
    assert not df.empty
    assert len(df) >= 8760
    assert "timestamp_utc" in df.columns
    assert "soil_moisture_5cm" in df.columns
    assert "soil_moisture_100cm" in df.columns
    assert "precip_mm" in df.columns
    assert "solar_rad_wm2" in df.columns


def test_uscrn_data_audit():
    df = parse_uscrn_file(USCRN_SAMPLE_PATH)
    report = audit_uscrn_dataframe(df, dataset_name="USCRN_2023_Lincoln", station_id="NE_Lincoln_11_SW")
    
    assert report.total_records >= 8760
    assert report.duplicate_timestamps == 0
    assert "soil_moisture_5cm" in report.variable_stats
    
    # Soil moisture 5cm should be within physical limits [0.0, 0.6] for valid records
    sm5_stats = report.variable_stats["soil_moisture_5cm"]
    if sm5_stats.non_null_count > 0:
        assert sm5_stats.min_value >= 0.0
        assert sm5_stats.max_value <= 0.60

    md_summary = report.to_markdown_summary()
    assert "Ingestion Audit Report" in md_summary


def test_uscrn_normalization_and_schema_validation():
    df = parse_uscrn_file(USCRN_SAMPLE_PATH)
    # Take first 50 records for contract validation speed
    sample_df = df.head(50)
    events = normalize_uscrn_dataframe(
        sample_df,
        source_id="USCRN_NE_Lincoln_11_SW",
        site_id="FIELD_LINCOLN_01",
        data_class=DataClass.OBSERVED,
    )

    assert len(events) == 50
    for evt in events:
        # Check natural key computation
        assert len(evt.natural_key) == 64
        # Validate against JSON schema
        assert_valid_payload("telemetry", evt.to_dict())
