"""
Command Line Interface for Agri Telemetry & Forecasting Platform.
Provides commands for running Phase 1 baseline, Phase 4 operational pipeline, streaming worker, and reproducibility verification.
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure package root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agri_telemetry.pipeline import Phase1Pipeline, OperationalPipeline

from agri_telemetry.config.settings import AppConfig
from agri_telemetry.ingestion import parse_uscrn_file, audit_uscrn_dataframe
from agri_telemetry.observability.metrics import platform_metrics
from agri_telemetry.streaming.broker import InMemoryStreamBroker, RedisStreamBroker
from agri_telemetry.streaming.worker import TelemetryStreamWorker


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


def run_operational_cmd(args: argparse.Namespace) -> None:
    data_file = Path(args.file)
    if not data_file.exists():
        print(f"Error: Data file not found at {data_file.resolve()}", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    config = AppConfig.from_yaml(args.config) if args.config else AppConfig.from_env()
    if args.station_id:
        config.station_id = args.station_id
    if args.site_id:
        config.site_id = args.site_id

    print("================================================================================")
    print("AGRI TELEMETRY & FORECASTING PLATFORM — PHASE 4 OPERATIONAL EXECUTION")
    print("================================================================================")
    print(f"Input Dataset:  {data_file.name}")
    print(f"Station ID:     {config.station_id}")
    print(f"Site ID:        {config.site_id}")
    print(f"Environment:    {config.observability.environment}")
    print(f"Log Format:     {config.observability.log_format}")
    print(f"MLOps Backend:  {config.mlops.tracking_backend}")
    print("--------------------------------------------------------------------------------")

    pipeline = OperationalPipeline(config=config)
    summary = pipeline.run_on_dataset(
        data_file=data_file,
        experiment_id=args.experiment_id,
        random_seed=args.seed,
    )

    print("Operational Pipeline Run Completed.")
    print(f"Run ID:                 {summary.run_id}")
    print(f"Total Ingested:         {summary.total_records:,}")
    print(f"Valid States:           {summary.valid_events_count:,}")
    print(f"Quarantined Records:    {summary.quarantined_events_count}")
    print(f"Forecast Events Emitted:{summary.forecast_events_count:,}")
    print(f"Alert Events Emitted:   {summary.alert_events_count}")
    print("--------------------------------------------------------------------------------")
    print(f"Run Summary persisted to: runs/{summary.run_id}/summary.json")
    print(f"Run Manifest persisted to: runs/{summary.run_id}/manifest.json")
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


def show_metrics_cmd(args: argparse.Namespace) -> None:
    print(json.dumps(platform_metrics.to_dict(), indent=2))


def reproducibility_cmd(args: argparse.Namespace) -> None:
    from agri_telemetry.experiments.reproducibility_check import run_reproducibility_verification
    print("Executing End-to-End Reproducibility Verification Experiment ...")
    success, details = run_reproducibility_verification(data_path=args.file)
    if success:
        print("\n[SUCCESS] Bit-for-bit and contract reproducibility verified across independent runs.")
        print(json.dumps(details, indent=2))
    else:
        print(f"\n[FAILURE] Reproducibility verification failed: {details}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agri-telemetry",
        description="Agri Telemetry & Forecasting Platform — Operational CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run-phase1
    run_p1 = subparsers.add_parser("run-phase1", help="Run Phase 1 baseline vertical slice")
    run_p1.add_argument(
        "--file",
        "-f",
        default="data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt",
        help="Path to USCRN hourly data file",
    )
    run_p1.add_argument("--station-id", default="USCRN_NE_Lincoln_11_SW", help="Station identifier")
    run_p1.add_argument("--site-id", default="FIELD_LINCOLN_01", help="Site/Field identifier")
    run_p1.add_argument("--seed", type=int, default=42, help="Deterministic random seed")

    # run-operational
    run_op = subparsers.add_parser("run-operational", help="Run Phase 4 operational pipeline with MLOps & Observability")
    run_op.add_argument(
        "--file",
        "-f",
        default="data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt",
        help="Path to USCRN hourly data file",
    )
    run_op.add_argument("--config", "-c", default=None, help="Path to YAML configuration file")
    run_op.add_argument("--experiment-id", default="EXP-PHASE4-OPERATIONAL", help="Experiment identifier")
    run_op.add_argument("--station-id", default=None, help="Override station identifier")
    run_op.add_argument("--site-id", default=None, help="Override site identifier")
    run_op.add_argument("--seed", type=int, default=42, help="Deterministic random seed")

    # audit
    audit_parser = subparsers.add_parser("audit", help="Audit USCRN dataset coverage and quality")
    audit_parser.add_argument(
        "--file",
        "-f",
        default="data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt",
        help="Path to USCRN hourly data file",
    )
    audit_parser.add_argument("--station-id", default="NE_Lincoln_11_SW", help="Station identifier")

    # show-metrics
    subparsers.add_parser("show-metrics", help="Print structured operational and scientific metrics")

    # reproducibility-check
    repro_parser = subparsers.add_parser("reproducibility-check", help="Run end-to-end reproducibility check")
    repro_parser.add_argument(
        "--file",
        "--data-file",
        "-f",
        dest="file",
        default=None,
        help="Path to USCRN hourly data file",
    )


    args = parser.parse_args()
    if args.command == "run-phase1":
        run_phase1_cmd(args)
    elif args.command == "run-operational":
        run_operational_cmd(args)
    elif args.command == "audit":
        audit_cmd(args)
    elif args.command == "show-metrics":
        show_metrics_cmd(args)
    elif args.command == "reproducibility-check":
        reproducibility_cmd(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
