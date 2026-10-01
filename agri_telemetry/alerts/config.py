"""
Risk Evaluation Configuration.
Configurable risk thresholds for agronomic decision support.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskEvaluationConfig:
    """Configurable agronomic risk thresholds."""
    d_mad: float = 0.50  # Management Allowable Depletion fraction [0.0 - 1.0]
    tau_risk: float = 0.75  # Uncertainty exceedance probability trigger [0.0 - 1.0]
    critical_wilting_depletion: float = 0.85  # Critical wilting proximity threshold
    crop_type: str = "Corn / Maize"
    growth_stage: str = "Mid-Season"

    def __post_init__(self):
        if not (0.0 <= self.d_mad <= 1.0):
            raise ValueError(f"d_mad must be in [0.0, 1.0], got {self.d_mad}")
        if not (0.0 <= self.tau_risk <= 1.0):
            raise ValueError(f"tau_risk must be in [0.0, 1.0], got {self.tau_risk}")
        if not (self.d_mad < self.critical_wilting_depletion <= 1.0):
            raise ValueError("critical_wilting_depletion must be > d_mad and <= 1.0")
