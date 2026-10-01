"""
SQLite Persistent Storage.
Stores canonical telemetry events, forecast emissions, alerts, and run summaries with deduplication.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, Dict, Any, List

from agri_telemetry.contracts.telemetry_event import TelemetryEvent
from agri_telemetry.contracts.forecast_event import ForecastEvent
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.domain.models import RunSummary


class SQLiteStore:
    """
    SQLite persistent storage with idempotent natural key deduplication.
    """

    def __init__(self, db_path: Union[str, Path] = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS telemetry_events (
                    event_id TEXT PRIMARY KEY,
                    natural_key TEXT UNIQUE NOT NULL,
                    source_id TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    ingest_time TEXT NOT NULL,
                    data_class TEXT NOT NULL,
                    is_quarantined INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS forecast_events (
                    forecast_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    forecast_origin_time TEXT NOT NULL,
                    target_variable TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alert_events (
                    alert_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    trigger_time TEXT NOT NULL,
                    is_autonomous_actuation INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS run_summaries (
                    run_id TEXT PRIMARY KEY,
                    dataset_name TEXT NOT NULL,
                    station_id TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    total_records INTEGER NOT NULL,
                    valid_events_count INTEGER NOT NULL,
                    quarantined_events_count INTEGER NOT NULL,
                    forecast_events_count INTEGER NOT NULL,
                    alert_events_count INTEGER NOT NULL,
                    summary_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry_events(event_time);
                CREATE INDEX IF NOT EXISTS idx_forecast_time ON forecast_events(forecast_origin_time);
                CREATE INDEX IF NOT EXISTS idx_alert_time ON alert_events(trigger_time);
            """)

    def store_telemetry_event(self, event: TelemetryEvent) -> bool:
        """
        Idempotently inserts a TelemetryEvent. Returns True if inserted, False if duplicate.
        """
        now_str = datetime.utcnow().isoformat()
        is_quarantined = 1 if (event.qc_summary and event.qc_summary.quarantined) else 0
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO telemetry_events 
                    (event_id, natural_key, source_id, site_id, event_time, ingest_time, data_class, is_quarantined, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.natural_key,
                        event.source_id,
                        event.site_id,
                        event.event_time,
                        event.ingest_time,
                        event.provenance.data_class.value,
                        is_quarantined,
                        event.to_json(),
                        now_str,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            # Duplicate natural key ignored
            return False

    def store_forecast_event(self, event: ForecastEvent) -> bool:
        now_str = datetime.utcnow().isoformat()
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO forecast_events 
                    (forecast_id, source_id, site_id, forecast_origin_time, target_variable, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.forecast_id,
                        event.source_id,
                        event.site_id,
                        event.forecast_origin_time,
                        event.target_variable.value,
                        event.to_json(),
                        now_str,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def store_alert_event(self, event: AlertEvent) -> bool:
        now_str = datetime.utcnow().isoformat()
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO alert_events 
                    (alert_id, category, severity, source_id, site_id, trigger_time, is_autonomous_actuation, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.alert_id,
                        event.category.value,
                        event.severity.value,
                        event.source_id,
                        event.site_id,
                        event.trigger_time,
                        1 if event.is_autonomous_actuation else 0,
                        event.to_json(),
                        now_str,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def store_run_summary(self, summary: RunSummary) -> bool:
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
        try:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO run_summaries 
                    (run_id, dataset_name, station_id, executed_at, total_records, valid_events_count, quarantined_events_count, forecast_events_count, alert_events_count, summary_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        summary.run_id,
                        summary.dataset_name,
                        summary.station_id,
                        summary.executed_at.isoformat(),
                        summary.total_records,
                        summary.valid_events_count,
                        summary.quarantined_events_count,
                        summary.forecast_events_count,
                        summary.alert_events_count,
                        json.dumps(summary_dict, indent=2),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_counts(self) -> Dict[str, int]:
        with self._conn:
            t_count = self._conn.execute("SELECT COUNT(*) FROM telemetry_events").fetchone()[0]
            q_count = self._conn.execute("SELECT COUNT(*) FROM telemetry_events WHERE is_quarantined = 1").fetchone()[0]
            f_count = self._conn.execute("SELECT COUNT(*) FROM forecast_events").fetchone()[0]
            a_count = self._conn.execute("SELECT COUNT(*) FROM alert_events").fetchone()[0]
            r_count = self._conn.execute("SELECT COUNT(*) FROM run_summaries").fetchone()[0]
        return {
            "telemetry_events": t_count,
            "quarantined_telemetry": q_count,
            "forecast_events": f_count,
            "alert_events": a_count,
            "run_summaries": r_count,
        }

    def close(self) -> None:
        self._conn.close()
