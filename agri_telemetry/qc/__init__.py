"""
Quality Control Package.
Tier-1 physical bounds, spike detection, flatline filters, and dead-letter quarantine.
"""

from agri_telemetry.qc.rules import (
    check_physical_range,
    check_vwc_spike,
    check_stuck_sensor,
    PHYSICAL_RANGES,
)
from agri_telemetry.qc.quarantine import (
    QuarantineBuffer,
    QuarantineRecord,
)
from agri_telemetry.qc.engine import Tier1QCEngine

__all__ = [
    "check_physical_range",
    "check_vwc_spike",
    "check_stuck_sensor",
    "PHYSICAL_RANGES",
    "QuarantineBuffer",
    "QuarantineRecord",
    "Tier1QCEngine",
]
