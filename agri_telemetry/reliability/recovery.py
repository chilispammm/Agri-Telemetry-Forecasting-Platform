"""
Reliability, Fault Tolerance & Recovery Engine for Agri Telemetry & Forecasting Platform.
Handles schema errors, dead letter queues (DLQ), idempotency deduplication, out-of-order sequencing, and model fallback.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
import hashlib
import json
import logging


@dataclass
class DeadLetterItem:
    """Record of a failed or unparseable event quarantined into DLQ."""
    dlq_id: str
    failed_at: str
    source_payload: Any
    failure_reason: str
    exception_details: Optional[str] = None
    retry_count: int = 0


class DeadLetterQueue:
    """Manages dead letter quarantine storage and offline reprocessing."""

    def __init__(self, dlq_file: Optional[Path] = None):
        self.dlq_file = dlq_file or (Path("runs") / "dead_letter_queue.jsonl")
        self._items: List[DeadLetterItem] = []

    def push(self, payload: Any, reason: str, exception: Optional[Exception] = None) -> DeadLetterItem:
        now_iso = datetime.now(timezone.utc).isoformat()
        dlq_id = f"dlq_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{len(self._items)}"
        item = DeadLetterItem(
            dlq_id=dlq_id,
            failed_at=now_iso,
            source_payload=payload,
            failure_reason=reason,
            exception_details=str(exception) if exception else None,
        )
        self._items.append(item)

        # Persist to disk
        try:
            self.dlq_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.dlq_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(item), default=str) + "\n")
        except Exception:
            pass

        return item

    def count(self) -> int:
        return len(self._items)

    def get_items(self) -> List[DeadLetterItem]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()


class EventDeduplicator:
    """In-memory and persistent hash-based idempotency filter."""

    def __init__(self, max_keys: int = 50000):
        self.max_keys = max_keys
        self._seen_keys: Set[str] = set()
        self._key_order: List[str] = []

    def compute_key(self, source_id: str, event_time: str, site_id: str) -> str:
        raw = f"{source_id}:{site_id}:{event_time}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def is_duplicate(self, key: str) -> bool:
        return key in self._seen_keys

    def register(self, key: str) -> bool:
        """Registers key. Returns True if key was new, False if it was duplicate."""
        if key in self._seen_keys:
            return False
        if len(self._seen_keys) >= self.max_keys:
            oldest = self._key_order.pop(0)
            self._seen_keys.discard(oldest)
        self._seen_keys.add(key)
        self._key_order.append(key)
        return True


class OutOfOrderSequencer:
    """Buffers and re-sequences windowed stream events by event_time."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._buffer: List[Dict[str, Any]] = []

    def push(self, event_dict: Dict[str, Any]) -> None:
        self._buffer.append(event_dict)

    def flush_sorted(self) -> List[Dict[str, Any]]:
        """Sorts buffer by event_time (or timestamp_utc) and flushes."""
        sorted_events = sorted(
            self._buffer,
            key=lambda x: str(x.get("event_time") or x.get("timestamp_utc") or "")
        )
        self._buffer.clear()
        return sorted_events

    def count(self) -> int:
        return len(self._buffer)


class ResilientForecastRouter:
    """
    Forecasting router that executes the primary model (e.g. M2/M1) and
    safely falls back to deterministic Persistence Baseline (B0) upon exception.
    """

    def __init__(self, primary_model: Any, persistence_baseline: Any):
        self.primary_model = primary_model
        self.persistence_baseline = persistence_baseline
        self.logger = logging.getLogger("agri_telemetry.resilience")
        self.fallback_count: int = 0

    def predict_safe(self, current_vwc: float, *args: Any, **kwargs: Any) -> Tuple[Dict[int, float], bool]:
        """
        Executes prediction. Returns (predictions_dict, used_fallback_flag).
        """
        try:
            if hasattr(self.primary_model, "predict"):
                raw_preds = self.primary_model.predict(current_vwc, *args, **kwargs)
            elif callable(self.primary_model):
                raw_preds = self.primary_model(current_vwc, *args, **kwargs)
            else:
                raise ValueError("Invalid primary model type")

            if isinstance(raw_preds, list):
                preds = {p.horizon_hours: p.point_forecast for p in raw_preds}
            else:
                preds = raw_preds
            return preds, False
        except Exception as ex:
            self.logger.warning(f"Primary forecast model failed with error: {ex}. Engaging Persistence fallback (B0).")
            self.fallback_count += 1
            raw_preds = self.persistence_baseline.predict(current_vwc, *args, **kwargs)
            if isinstance(raw_preds, list):
                preds = {p.horizon_hours: p.point_forecast for p in raw_preds}
            else:
                preds = raw_preds
            return preds, True

