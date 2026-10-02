"""
MLOps Experiment Lifecycle & Model Metadata Tracker.
Supports both canonical local JSON ledger tracking and optional local MLflow integration.
Tracks complete lineage: data version, code SHA, hyperparams, seeds, splits, metrics, and artefacts.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import json
import os
import subprocess


def get_git_commit_sha() -> str:
    """Retrieves current Git commit SHA or returns fallback if unavailable."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent.parent.parent,
        )
        return res.stdout.strip()
    except Exception:
        return "git-commit-unknown"


@dataclass
class ExperimentRunManifest:
    """Standardized metadata manifest for an experimental or operational run."""
    run_id: str
    experiment_id: str
    created_at: str
    git_commit_sha: str
    dataset_name: str
    dataset_version: str
    station_id: str
    site_id: str
    target_variable: str
    horizons: List[int]
    features: List[str]
    model_name: str
    hyperparameters: Dict[str, Any]
    split_strategy: str
    train_window: Dict[str, str]
    test_window: Dict[str, str]
    random_seed: int
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)


class ExperimentRunContext:
    """Active run context manager for logging metadata and metrics."""

    def __init__(
        self,
        tracker: "ExperimentTracker",
        run_id: str,
        experiment_id: str,
        dataset_name: str = "USCRN_Lincoln_11_SW",
        dataset_version: str = "2023_hourly",
        station_id: str = "USCRN_NE_Lincoln_11_SW",
        site_id: str = "FIELD_LINCOLN_01",
        target_variable: str = "volumetric_water_content",
        horizons: Optional[List[int]] = None,
        features: Optional[List[str]] = None,
        model_name: str = "PERSISTENCE_BASELINE",
        hyperparameters: Optional[Dict[str, Any]] = None,
        split_strategy: str = "Chronological Walk-Forward",
        train_window: Optional[Dict[str, str]] = None,
        test_window: Optional[Dict[str, str]] = None,
        random_seed: int = 42,
    ):
        self.tracker = tracker
        self.manifest = ExperimentRunManifest(
            run_id=run_id,
            experiment_id=experiment_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            git_commit_sha=get_git_commit_sha(),
            dataset_name=dataset_name,
            dataset_version=dataset_version,
            station_id=station_id,
            site_id=site_id,
            target_variable=target_variable,
            horizons=horizons or [1, 6, 12, 24, 48, 72, 168],
            features=features or ["soil_moisture_lag_1h"],
            model_name=model_name,
            hyperparameters=hyperparameters or {},
            split_strategy=split_strategy,
            train_window=train_window or {},
            test_window=test_window or {},
            random_seed=random_seed,
        )

    def log_param(self, key: str, value: Any) -> None:
        self.manifest.hyperparameters[key] = value

    def log_params(self, params: Dict[str, Any]) -> None:
        self.manifest.hyperparameters.update(params)

    def log_metric(self, key: str, value: float) -> None:
        self.manifest.metrics[key] = value

    def log_metrics(self, metrics: Dict[str, float]) -> None:
        self.manifest.metrics.update(metrics)

    def log_artifact(self, artifact_path: str | Path) -> None:
        p = str(Path(artifact_path).as_posix())
        if p not in self.manifest.artifacts:
            self.manifest.artifacts.append(p)

    def set_tag(self, key: str, value: str) -> None:
        self.manifest.tags[key] = value

    def set_tags(self, tags: Dict[str, str]) -> None:
        self.manifest.tags.update(tags)

    def __enter__(self) -> "ExperimentRunContext":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.manifest.tags["status"] = "FAILED"
            self.manifest.tags["error"] = str(exc_val)
        else:
            self.manifest.tags["status"] = "COMPLETED"
        self.tracker.save_manifest(self.manifest)


class ExperimentTracker:
    """
    Unified Experiment and Model Lifecycle Tracker.
    Manages structured experiment runs, metadata serialization, and local ledger synchronization.
    """

    def __init__(
        self,
        runs_dir: str | Path = "runs",
        backend: str = "LOCAL_LEDGER",
        mlflow_uri: Optional[str] = None,
    ):
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.backend = backend.upper()
        self.mlflow_uri = mlflow_uri

    def start_run(
        self,
        run_id: str,
        experiment_id: str = "EXP-DEFAULT",
        **kwargs: Any,
    ) -> ExperimentRunContext:
        """Starts a new tracked experiment run context."""
        return ExperimentRunContext(
            tracker=self,
            run_id=run_id,
            experiment_id=experiment_id,
            **kwargs,
        )

    def save_manifest(self, manifest: ExperimentRunManifest) -> Path:
        """Saves run manifest JSON to run artifact directory."""
        run_folder = self.runs_dir / manifest.run_id
        run_folder.mkdir(parents=True, exist_ok=True)
        manifest_path = run_folder / "manifest.json"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(asdict(manifest), f, indent=2)

        # Also log to MLflow if enabled and configured
        if self.backend == "MLFLOW" and self.mlflow_uri:
            self._log_to_mlflow(manifest)

        return manifest_path

    def _log_to_mlflow(self, manifest: ExperimentRunManifest) -> None:
        """Logs manifest metadata to local MLflow backend if available."""
        try:
            import mlflow
            mlflow.set_tracking_uri(self.mlflow_uri)
            mlflow.set_experiment(manifest.experiment_id)
            with mlflow.start_run(run_name=manifest.run_id):
                mlflow.log_params(manifest.hyperparameters)
                mlflow.log_params({
                    "dataset_name": manifest.dataset_name,
                    "dataset_version": manifest.dataset_version,
                    "station_id": manifest.station_id,
                    "model_name": manifest.model_name,
                    "git_commit_sha": manifest.git_commit_sha,
                    "random_seed": manifest.random_seed,
                })
                # Log scalar metrics
                for k, v in manifest.metrics.items():
                    if isinstance(v, (int, float)):
                        mlflow.log_metric(k, float(v))
                for art in manifest.artifacts:
                    if Path(art).exists():
                        mlflow.log_artifact(art)
        except Exception:
            # Fallback gracefully if MLflow server is not reachable
            pass
