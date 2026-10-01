"""
Evidence Ledger and Run Artifacts Management.
Persists immutable execution summaries and updates Evidence & Validation records.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from agri_telemetry.domain.models import RunSummary


class EvidenceLedger:
    """
    Manages run artifacts and execution verification ledgers.
    """

    def __init__(self, runs_root: Optional[Path] = None):
        self.runs_root = runs_root or (Path(__file__).parent.parent.parent / "runs")
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def record_run(self, summary: RunSummary) -> Path:
        """
        Writes run artifacts: runs/<run_id>/summary.json and updates evidence_ledger.md.
        """
        run_dir = self.runs_root / summary.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        summary_dict = {
            "run_id": summary.run_id,
            "executed_at": summary.executed_at.isoformat(),
            "dataset_name": summary.dataset_name,
            "station_id": summary.station_id,
            "start_time": summary.start_time.isoformat(),
            "end_time": summary.end_time.isoformat(),
            "total_records": summary.total_records,
            "valid_events_count": summary.valid_events_count,
            "quarantined_events_count": summary.quarantined_events_count,
            "forecast_events_count": summary.forecast_events_count,
            "alert_events_count": summary.alert_events_count,
            "persistence_mae": summary.persistence_mae,
            "persistence_rmse": summary.persistence_rmse,
            "persistence_skill": summary.persistence_skill,
            "interval_80_coverage": summary.interval_80_coverage,
            "random_seed": summary.random_seed,
            "config": summary.config,
        }

        # Write summary.json
        summary_file = run_dir / "summary.json"
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_dict, f, indent=2)

        # Update evidence_ledger.md
        ledger_file = self.runs_root / "evidence_ledger.md"
        entry_md = self._format_ledger_entry(summary)

        with open(ledger_file, "a", encoding="utf-8") as f:
            f.write(entry_md + "\n\n---\n\n")

        return summary_file

    def _format_ledger_entry(self, s: RunSummary) -> str:
        lines = [
            f"## Run Execution `{s.run_id}`",
            f"- **Executed At (UTC)**: `{s.executed_at.isoformat()}`",
            f"- **Dataset**: `{s.dataset_name}` (`{s.station_id}`)",
            f"- **Time Range**: `{s.start_time.isoformat()}` to `{s.end_time.isoformat()}`",
            f"- **Total Ingested Records**: `{s.total_records:,}`",
            f"- **Valid Events**: `{s.valid_events_count:,}`",
            f"- **Quarantined Events**: `{s.quarantined_events_count}`",
            f"- **Emitted Forecast Events**: `{s.forecast_events_count:,}`",
            f"- **Emitted Alert Events**: `{s.alert_events_count}` (Autonomous Actuation: **False**)",
            "",
            "### Out-of-Sample Persistence Benchmark Metrics",
            "| Horizon | MAE (m³/m³) | RMSE (m³/m³) | 80% PI Coverage | Skill vs Climatology |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for h in sorted(s.persistence_mae.keys()):
            mae_v = s.persistence_mae[h]
            rmse_v = s.persistence_rmse[h]
            cov_v = s.interval_80_coverage.get(h, 0.0) * 100
            skill_v = s.persistence_skill.get(h, 0.0)
            lines.append(
                f"| `{h}h` | {mae_v:.4f} | {rmse_v:.4f} | {cov_v:.1f}% | {skill_v:+.3f} |"
            )

        return "\n".join(lines)
