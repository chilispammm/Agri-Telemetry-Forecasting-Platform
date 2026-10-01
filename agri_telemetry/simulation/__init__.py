"""
Simulation and Synthetic Fault Injection Package.
"""

from agri_telemetry.simulation.fault_injector import (
    FaultSpec,
    inject_synthetic_faults,
)

__all__ = [
    "FaultSpec",
    "inject_synthetic_faults",
]
