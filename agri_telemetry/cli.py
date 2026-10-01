"""
Command Line Interface for Agri Telemetry & Forecasting Platform.
Provides commands for running the Phase 1 Vertical Slice, data auditing, and verification.
"""

import argparse
import sys
from pathlib import Path

from agri_telemetry.pipeline import Phase1Pipeline
from agri_telemetry.ingestion import parse_uscrn_file, audit_uscrn_dataframe


def run_phase1_cmd(args: argparse.Namespace) -> None:
    data_file = Path(args.file)
    if not data_file.exists():
        print(f"Error: Data file not found at {data_file.resolve()}", file=sys.stderr)
        sys.exit(1)

    print("================================================================================")
    print("AGRI TELEMETRY & FORECASTING PLATFORM — PHASE 1 VERTICAL SLICE EXECUTION")
    print("================================================================================")
    print(f"Input Dataset:  {data_file.name}")
    print(f"Station ID:     {args.station_id}")
    print(f"Site ID:        {args.site_id}")
    print(f"Random Seed:    {args.seed}")
    print("--------------------------------------------------------------------------------")

    pipeline = Phase1Pipeline()
    summary = pipeline.run_on_dataset(
        data_file=data_file,
        station_id=args.station_id,
        site_id=args.site_id,
        dataset_name=data_file.stem,
        random_seed=args.seed,
    )

    print("Pipeline Execution Completed Successfully.")
    print(f"Run ID:                 {summary.run_id}")
    print(f"Total Ingested Records: {summary.total_records:,}")
    print(f"Valid States Built:     {summary.valid_events_count:,}")
    print(f"Quarantined Records:    {summary.quarantined_events_count}")
    print(f"Forecast Events Emitted:{summary.forecast_events_count:,}")
    print(f"Alert Events Emitted:   {summary.alert_events_count}")
    print("--------------------------------------------------------------------------------")
    print("Out-of-Sample Persistence Forecast Verification:")
    print(f"{'Horizon':<10} {'MAE (m3/m3)':<15} {'RMSE (m3/m3)':<15} {'80% Coverage':<15} {'Skill vs Mean':<15}")
    for h in sorted(summary.persistence_mae.keys()):
        mae_v = summary.persistence_mae[h]
        rmse_v = summary.persistence_rmse[h]
        cov_v = summary.interval_80_coverage.get(h, 0.0) * 100
        skill_v = summary.persistence_skill.get(h, 0.0)
        print(f"{str(h) + 'h':<10} {mae_v:<15.4f} {rmse_v:<15.4f} {f'{cov_v:.1f}%':<15} {f'{skill_v:+.3f}':<15}")
    print("================================================================================")
    print(f"Run Summary persisted to: runs/{summary.run_id}/summary.json")
    print("Evidence ledger updated:  runs/evidence_ledger.md")


def audit_cmd(args: argparse.Namespace) -> None:
    data_file = Path(args.file)
    if not data_file.exists():
        print(f"Error: Data file not found at {data_file.resolve()}", file=sys.stderr)
        sys.exit(1)

    print(f"Auditing USCRN dataset: {data_file.resolve()} ...")
    df = parse_uscrn_file(data_file)
    report = audit_uscrn_dataframe(df, dataset_name=data_file.stem, station_id=args.station_id)
    print("\n" + report.to_markdown_summary())


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agri-telemetry",
        description="Agri Telemetry & Forecasting Platform — Minimum Reproducible Vertical Slice",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run-phase1
    run_parser = subparsers.add_parser("run-phase1", help="Run Phase 1 vertical slice on historical data")
    run_parser.add_argument(
        "--file",
        "-f",
        default="data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt",
        help="Path to USCRN hourly data file",
    )
    run_parser.add_argument("--station-id", default="USCRN_NE_Lincoln_11_SW", help="Station identifier")
    run_parser.add_argument("--site-id", default="FIELD_LINCOLN_01", help="Site/Field identifier")
    run_parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")

    # audit
    audit_parser = subparsers.add_parser("audit", help="Audit USCRN dataset coverage and quality")
    audit_parser.add_argument(
        "--file",
        "-f",
        default="data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt",
        help="Path to USCRN hourly data file",
    )
    audit_parser.add_argument("--station-id", default="NE_Lincoln_11_SW", help="Station identifier")

    args = parser.parse_args()
    if args.command == "run-phase1":
        run_phase1_cmd(args)
    elif args.command == "audit":
        audit_cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
