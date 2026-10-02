"""
Synthetic simulation and fault injection suite for Agri Telemetry & Forecasting Platform.
"""

from agri_telemetry.simulation.fault_injector import (
    FaultSpec,
    inject_synthetic_faults,
)
from agri_telemetry.simulation.scenarios import (
    ScenarioStep,
    SyntheticScenario,
    build_synthetic_scenarios,
)
from agri_telemetry.simulation.scenario_runner import (
    SyntheticScenarioRunner,
    ScenarioEvaluationResult,
)

__all__ = [
    "FaultSpec",
    "inject_synthetic_faults",
    "ScenarioStep",
    "SyntheticScenario",
    "build_synthetic_scenarios",
    "SyntheticScenarioRunner",
    "ScenarioEvaluationResult",
]
