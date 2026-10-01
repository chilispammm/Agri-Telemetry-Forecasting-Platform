"""
Soil Physical and Profile Parameters.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class SoilProfileConfig:
    """Soil physical limits and root-zone configuration."""
    theta_sat: float = 0.45  # Saturated water content (m3/m3)
    theta_fc: float = 0.32   # Field capacity (m3/m3)
    theta_wp: float = 0.14   # Permanent wilting point (m3/m3)
    root_depth_cm: float = 100.0  # Root-zone depth in cm
    
    # Layer weights for USCRN depths [5, 10, 20, 50, 100 cm]
    layer_weights: Dict[float, float] = field(
        default_factory=lambda: {
            5.0: 0.075,
            10.0: 0.075,
            20.0: 0.200,
            50.0: 0.400,
            100.0: 0.250,
        }
    )

    def __post_init__(self):
        if not (self.theta_sat > self.theta_fc > self.theta_wp >= 0.0):
            raise ValueError(
                f"Invalid soil parameters: require theta_sat ({self.theta_sat}) > "
                f"theta_fc ({self.theta_fc}) > theta_wp ({self.theta_wp}) >= 0"
            )
        weight_sum = sum(self.layer_weights.values())
        if not (0.99 <= weight_sum <= 1.01):
            raise ValueError(f"Layer weights must sum to 1.0, got {weight_sum}")

    @property
    def total_available_water_mm(self) -> float:
        """TAW = 10 * root_depth_cm * (theta_fc - theta_wp) (equivalent to 1000 * Zr_m * delta_theta)."""
        return 10.0 * self.root_depth_cm * (self.theta_fc - self.theta_wp)

