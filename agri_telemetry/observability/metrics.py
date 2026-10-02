"""
Operational & Scientific Metrics Collector for Agri Telemetry & Forecasting Platform.
Separates operational system metrics (latency, error rate, throughput) from business/scientific metrics (forecast skill, coverage, depletion).
"""

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Any, Optional
import numpy as np


class LatencyTracker:
    """Tracks latency percentiles using in-memory sample buffer."""

    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
        self._samples: List[float] = []
        self._lock = Lock()

    def record(self, latency_ms: float) -> None:
        with self._lock:
            if len(self._samples) >= self.max_samples:
                self._samples.pop(0)
            self._samples.append(latency_ms)

    def summary(self) -> Dict[str, float]:
        with self._lock:
            if not self._samples:
                return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
            arr = np.array(self._samples)
            return {
                "count": float(len(arr)),
                "mean": float(np.mean(arr)),
                "min": float(np.min(arr)),
                "max": float(np.max(arr)),
                "p50": float(np.percentile(arr, 50)),
                "p90": float(np.percentile(arr, 90)),
                "p95": float(np.percentile(arr, 95)),
                "p99": float(np.percentile(arr, 99)),
            }

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()


class MetricsCollector:
    """Thread-safe collector for system/operational and business/scientific metrics."""

    def __init__(self):
        self._lock = Lock()

        # 1. Operational / System Metrics
        self.events_ingested_total: int = 0
        self.events_valid_total: int = 0
        self.events_quarantined_total: int = 0
        self.forecasts_generated_total: int = 0
        self.advisories_emitted_total: int = 0
        self.errors_total: int = 0
        self.pipeline_latency = LatencyTracker()
        self.stage_latencies: Dict[str, LatencyTracker] = {}

        # 2. Business / Scientific Metrics
        self.forecast_mae: Dict[int, float] = {}
        self.forecast_rmse: Dict[int, float] = {}
        self.interval_80_coverage: Dict[int, float] = {}
        self.skill_vs_persistence: Dict[int, float] = {}
        self.latest_depletion_fraction: float = 0.0
        self.advisories_by_category: Dict[str, int] = {
            "AGRONOMIC_RISK": 0,
            "DATA_QUALITY_ALERT": 0,
            "PHYSICAL_DEVIATION": 0,
        }
        self.advisories_by_severity: Dict[str, int] = {
            "INFO": 0,
            "WARNING": 0,
            "CRITICAL": 0,
        }

    def record_ingested_event(self, valid: bool = True) -> None:
        with self._lock:
            self.events_ingested_total += 1
            if valid:
                self.events_valid_total += 1

    def record_quarantine(self, count: int = 1) -> None:
        with self._lock:
            self.events_quarantined_total += count

    def record_forecast_emitted(self, count: int = 1) -> None:
        with self._lock:
            self.forecasts_generated_total += count

    def record_advisory_emitted(self, category: str, severity: str) -> None:
        with self._lock:
            self.advisories_emitted_total += 1
            self.advisories_by_category[category] = self.advisories_by_category.get(category, 0) + 1
            self.advisories_by_severity[severity] = self.advisories_by_severity.get(severity, 0) + 1

    def record_error(self, count: int = 1) -> None:
        with self._lock:
            self.errors_total += count

    def record_pipeline_latency(self, duration_ms: float) -> None:
        self.pipeline_latency.record(duration_ms)

    def record_stage_latency(self, stage_name: str, duration_ms: float) -> None:
        with self._lock:
            if stage_name not in self.stage_latencies:
                self.stage_latencies[stage_name] = LatencyTracker()
        self.stage_latencies[stage_name].record(duration_ms)

    def record_scientific_metrics(
        self,
        mae: Optional[Dict[int, float]] = None,
        rmse: Optional[Dict[int, float]] = None,
        coverage: Optional[Dict[int, float]] = None,
        skill: Optional[Dict[int, float]] = None,
        latest_depletion: Optional[float] = None,
    ) -> None:
        with self._lock:
            if mae:
                self.forecast_mae.update(mae)
            if rmse:
                self.forecast_rmse.update(rmse)
            if coverage:
                self.interval_80_coverage.update(coverage)
            if skill:
                self.skill_vs_persistence.update(skill)
            if latest_depletion is not None:
                self.latest_depletion_fraction = latest_depletion

    def to_dict(self) -> Dict[str, Any]:
        """Returns structured dictionary of all operational and scientific metrics."""
        with self._lock:
            stages_summary = {k: v.summary() for k, v in self.stage_latencies.items()}
            return {
                "operational_metrics": {
                    "events_ingested_total": self.events_ingested_total,
                    "events_valid_total": self.events_valid_total,
                    "events_quarantined_total": self.events_quarantined_total,
                    "quarantine_rate_percent": (
                        (self.events_quarantined_total / max(1, self.events_ingested_total)) * 100.0
                    ),
                    "forecasts_generated_total": self.forecasts_generated_total,
                    "advisories_emitted_total": self.advisories_emitted_total,
                    "errors_total": self.errors_total,
                    "pipeline_latency_ms": self.pipeline_latency.summary(),
                    "stage_latencies_ms": stages_summary,
                },
                "scientific_metrics": {
                    "forecast_mae": self.forecast_mae,
                    "forecast_rmse": self.forecast_rmse,
                    "interval_80_coverage": self.interval_80_coverage,
                    "skill_vs_persistence": self.skill_vs_persistence,
                    "latest_depletion_fraction": self.latest_depletion_fraction,
                    "advisories_by_category": self.advisories_by_category,
                    "advisories_by_severity": self.advisories_by_severity,
                },
            }

    def reset(self) -> None:
        """Resets all metrics counters and samples."""
        with self._lock:
            self.events_ingested_total = 0
            self.events_valid_total = 0
            self.events_quarantined_total = 0
            self.forecasts_generated_total = 0
            self.advisories_emitted_total = 0
            self.errors_total = 0
            self.pipeline_latency.reset()
            self.stage_latencies.clear()
            self.forecast_mae.clear()
            self.forecast_rmse.clear()
            self.interval_80_coverage.clear()
            self.skill_vs_persistence.clear()
            self.latest_depletion_fraction = 0.0
            self.advisories_by_category = {"AGRONOMIC_RISK": 0, "DATA_QUALITY_ALERT": 0, "PHYSICAL_DEVIATION": 0}
            self.advisories_by_severity = {"INFO": 0, "WARNING": 0, "CRITICAL": 0}


# Global singleton instance for platform metrics
platform_metrics = MetricsCollector()
