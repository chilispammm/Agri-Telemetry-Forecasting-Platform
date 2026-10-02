"""
Structured JSON Logging & Tracing for Agri Telemetry & Forecasting Platform.
Provides correlation ID propagation, execution stage timing, and structured log formatting.
"""

import json
import logging
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional


# Context variables for request / cycle correlation
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
run_id_ctx: ContextVar[Optional[str]] = ContextVar("run_id", default=None)
stage_ctx: ContextVar[Optional[str]] = ContextVar("stage", default=None)


class JSONFormatter(logging.Formatter):
    """Formats logging records into standardized JSON objects."""

    def __init__(self, service_name: str = "agri-telemetry-platform", environment: str = "development"):
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
            "environment": self.environment,
            "correlation_id": correlation_id_ctx.get(),
            "run_id": run_id_ctx.get(),
            "stage": stage_ctx.get(),
        }

        # Include custom extra fields
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            log_entry.update(record.extra_fields)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logger(
    name: str = "agri_telemetry",
    level: str = "INFO",
    log_format: str = "json",
    service_name: str = "agri-telemetry-platform",
    environment: str = "development",
) -> logging.Logger:
    """Configures and returns a structured logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    if log_format.lower() == "json":
        handler.setFormatter(JSONFormatter(service_name=service_name, environment=environment))
    else:
        fmt = "%(asctime)s [%(levelname)s] [%(name)s] [stage=%(stage)s] %(message)s"
        handler.setFormatter(logging.Formatter(fmt))

    logger.addHandler(handler)
    logger.propagate = False
    return logger


@contextmanager
def trace_stage(stage_name: str, logger: Optional[logging.Logger] = None, extra: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager to trace execution duration of a pipeline stage.
    """
    prev_stage = stage_ctx.get()
    stage_ctx.set(stage_name)
    start_time = time.perf_counter()
    ctx_info: Dict[str, Any] = {"stage": stage_name, "start_time": start_time}

    log = logger or logging.getLogger("agri_telemetry")
    log.debug(f"Starting stage: {stage_name}", extra={"extra_fields": extra or {}})

    try:
        yield ctx_info
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        ctx_info["elapsed_ms"] = elapsed_ms
        stage_ctx.set(prev_stage)
        log.debug(f"Completed stage: {stage_name} in {elapsed_ms:.2f}ms", extra={"extra_fields": {"duration_ms": elapsed_ms, **(extra or {})}})


def set_correlation_id(corr_id: str) -> None:
    """Sets the active correlation ID in context."""
    correlation_id_ctx.set(corr_id)


def set_run_id(r_id: str) -> None:
    """Sets the active run ID in context."""
    run_id_ctx.set(r_id)
