"""
Root-Zone Depth Integration.
Integrates multi-depth soil moisture observations into effective root-zone volumetric water content theta_rz.
"""

from typing import Dict, Optional, Tuple


def integrate_root_zone_moisture(
    depth_vwc: Dict[float, Optional[float]],
    weights: Dict[float, float],
    min_valid_weight_fraction: float = 0.50,
) -> Tuple[Optional[float], float, bool]:
    """
    Computes effective root-zone water content theta_rz from depth layers.
    
    Returns:
        (theta_rz: Optional[float], valid_weight_fraction: float, is_reliable: bool)
    """
    valid_depths = {
        d: v for d, v in depth_vwc.items()
        if v is not None and d in weights
    }

    if not valid_depths:
        return None, 0.0, False

    valid_weight_sum = sum(weights[d] for d in valid_depths.keys())
    
    if valid_weight_sum <= 0.0:
        return None, 0.0, False

    # Weighted sum normalized by available layer weight sum
    theta_rz = sum(
        (weights[d] / valid_weight_sum) * valid_depths[d]
        for d in valid_depths.keys()
    )

    is_reliable = (valid_weight_sum >= min_valid_weight_fraction)

    return float(theta_rz), float(valid_weight_sum), is_reliable
