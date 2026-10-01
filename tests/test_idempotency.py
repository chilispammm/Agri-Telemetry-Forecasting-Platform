"""
Unit Tests for Storage Idempotency and Deduplication.
"""

from datetime import datetime, timezone
import pytest

from agri_telemetry.contracts import TelemetryEvent, TelemetryMeasurement
from agri_telemetry.domain.enums import VariableName, Unit, DataClass
from agri_telemetry.storage import SQLiteStore


def test_sqlite_telemetry_deduplication():
    store = SQLiteStore(":memory:")

    now = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    measurements = [
        TelemetryMeasurement(
            sensor_id="SOIL_VWC_5CM",
            variable_name=VariableName.VOLUMETRIC_WATER_CONTENT,
            depth_cm=5.0,
            value=0.28,
            unit=Unit.M3_M3,
        )
    ]

    event1 = TelemetryEvent.create_new(
        source_id="STATION_01",
        site_id="FIELD_01",
        event_time=now,
        measurements=measurements,
        data_class=DataClass.OBSERVED,
    )

    # First insert -> succeeds
    assert store.store_telemetry_event(event1) is True

    # Construct second event with same natural key (same source, time, data_class, schema_version)
    event2 = TelemetryEvent.create_new(
        source_id="STATION_01",
        site_id="FIELD_01",
        event_time=now,
        measurements=measurements,
        data_class=DataClass.OBSERVED,
    )

    # Second insert with identical natural key -> deduplicated (returns False, does not crash)
    assert store.store_telemetry_event(event2) is False

    # Store count remains 1
    counts = store.get_counts()
    assert counts["telemetry_events"] == 1
