"""
End-to-End Integration Tests for Phase 1 Vertical Slice Pipeline.
"""

from pathlib import Path
import pytest

from agri_telemetry.pipeline import Phase1Pipeline
from agri_telemetry.storage import SQLiteStore

USCRN_DATA_FILE = Path(__file__).parent.parent / "data" / "uscrn" / "CRNH0203-2023-NE_Lincoln_11_SW.txt"


def test_phase1_pipeline_end_to_end(tmp_path):
    assert USCRN_DATA_FILE.exists()

    db_path = tmp_path / "test_agri.db"
    runs_dir = tmp_path / "runs"

    pipeline = Phase1Pipeline(db_path=db_path, runs_dir=runs_dir)

    # Run pipeline on a subset of 500 records for fast end-to-end testing
    summary = pipeline.run_on_dataset(
        data_file=USCRN_DATA_FILE,
        station_id="USCRN_NE_Lincoln_11_SW",
        site_id="FIELD_LINCOLN_01",
        dataset_name="USCRN_2023_Lincoln",
        max_records=500,
        random_seed=42,
    )

    assert summary.total_records == 500
    assert summary.valid_events_count >= 300
    assert summary.forecast_events_count >= 100
    assert (runs_dir / summary.run_id / "summary.json").exists()

    assert (runs_dir / "evidence_ledger.md").exists()

    # Verify SQLite database
    store = SQLiteStore(db_path)
    counts = store.get_counts()
    assert counts["telemetry_events"] == 500
    assert counts["forecast_events"] == summary.forecast_events_count
    assert counts["run_summaries"] == 1
