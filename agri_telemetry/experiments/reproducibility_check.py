"""
End-to-End Reproducibility Verification Experiment for Phase 4.
Runs two independent pipeline executions on the fixed historical USCRN dataset with fixed seed and compares all outputs.
"""

from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import tempfile

import numpy as np

from agri_telemetry.config.settings import AppConfig
from agri_telemetry.pipeline import OperationalPipeline


def run_reproducibility_verification(data_path: Optional[str | Path] = None) -> Tuple[bool, Dict[str, Any]]:
    """
    Executes two identical operational pipeline runs in isolated temporary workspaces
    and asserts bit-for-bit and metric equivalence.
    """
    if data_path:
        data_file = Path(data_path)
    else:
        data_file = Path("data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt")
        if not data_file.exists():
            data_file = Path(__file__).parent.parent.parent / "data" / "uscrn" / "CRNH0203-2023-NE_Lincoln_11_SW.txt"


    with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
        # Run 1
        cfg1 = AppConfig()
        cfg1.storage.db_path = str(Path(tmpdir1) / "test1.db")
        cfg1.storage.runs_dir = str(Path(tmpdir1) / "runs")
        cfg1.forecasting.random_seed = 42

        pipeline1 = OperationalPipeline(config=cfg1)
        res1 = pipeline1.run_on_dataset(
            data_file=data_file,
            experiment_id="EXP-REPRODUCIBILITY-RUN-1",
            random_seed=42,
        )
        pipeline1.close()

        # Run 2
        cfg2 = AppConfig()
        cfg2.storage.db_path = str(Path(tmpdir2) / "test2.db")
        cfg2.storage.runs_dir = str(Path(tmpdir2) / "runs")
        cfg2.forecasting.random_seed = 42

        pipeline2 = OperationalPipeline(config=cfg2)
        res2 = pipeline2.run_on_dataset(
            data_file=data_file,
            experiment_id="EXP-REPRODUCIBILITY-RUN-2",
            random_seed=42,
        )
        pipeline2.close()

        # Compare metrics and counts
        checks = {
            "total_records_match": res1.total_records == res2.total_records,
            "valid_events_match": res1.valid_events_count == res2.valid_events_count,
            "quarantined_events_match": res1.quarantined_events_count == res2.quarantined_events_count,
            "forecast_events_match": res1.forecast_events_count == res2.forecast_events_count,
            "alert_events_match": res1.alert_events_count == res2.alert_events_count,
        }

        mae_diffs = []
        rmse_diffs = []
        for h in res1.persistence_mae.keys():
            mae_diff = abs(res1.persistence_mae[h] - res2.persistence_mae[h])
            rmse_diff = abs(res1.persistence_rmse[h] - res2.persistence_rmse[h])
            mae_diffs.append(mae_diff)
            rmse_diffs.append(rmse_diff)

        checks["max_mae_discrepancy"] = float(max(mae_diffs))
        checks["max_rmse_discrepancy"] = float(max(rmse_diffs))
        checks["metrics_identical"] = max(mae_diffs) < 1e-9 and max(rmse_diffs) < 1e-9

        all_passed = (
            checks["total_records_match"]
            and checks["valid_events_match"]
            and checks["quarantined_events_match"]
            and checks["forecast_events_match"]
            and checks["alert_events_match"]
            and checks["metrics_identical"]
        )

        details = {
            "is_reproducible": all_passed,
            "run1_records": res1.total_records,
            "run2_records": res2.total_records,
            "run1_forecasts": res1.forecast_events_count,
            "run2_forecasts": res2.forecast_events_count,
            "run1_alerts": res1.alert_events_count,
            "run2_alerts": res2.alert_events_count,
            "checks": checks,
        }

        return all_passed, details


if __name__ == "__main__":
    passed, det = run_reproducibility_verification()
    print("Reproducibility verification:", "PASSED" if passed else "FAILED")
    print(det)
