"""
Root-Zone Depletion and Storage Metrics.
Computes Dr (depletion fraction), FAW (fraction of available water), storage, and deficit in millimeters.
"""

from typing import Tuple


def calculate_depletion_fraction(theta_rz: float, theta_fc: float, theta_wp: float) -> float:
    """
    Computes root-zone soil water depletion fraction:
    Dr = (theta_fc - theta_rz) / (theta_fc - theta_wp)
    
    Dr = 0.0 at Field Capacity (no stress).
    Dr = 0.50 at typical Management Allowable Depletion (MAD).
    Dr = 1.0 at Permanent Wilting Point (critical stress).
    Dr < 0.0 during saturation / ponding.
    """
    available_range = theta_fc - theta_wp
    if available_range <= 0.0:
        raise ValueError("theta_fc must be strictly greater than theta_wp")
    return (theta_fc - theta_rz) / available_range


def calculate_available_water_fraction(theta_rz: float, theta_fc: float, theta_wp: float) -> float:
    """
    Computes fraction of available water (FAW):
    FAW = (theta_rz - theta_wp) / (theta_fc - theta_wp) = 1.0 - Dr
    """
    return 1.0 - calculate_depletion_fraction(theta_rz, theta_fc, theta_wp)


def calculate_storage_and_deficit_mm(
    theta_rz: float,
    theta_fc: float,
    root_depth_cm: float,
) -> Tuple[float, float]:
    """
    Computes root-zone water storage (mm) and irrigation deficit (mm).
    
    Storage = 10 * (root_depth_cm / 1.0) * theta_rz / 100 * 100 = 10 * root_depth_cm * theta_rz (in mm)
    Deficit = 10 * root_depth_cm * max(0.0, theta_fc - theta_rz) (in mm)
    """
    # 1 m3 water / m3 soil over 1 cm depth = 10 mm depth of water
    # So for depth in cm, depth_mm = depth_cm * 10
    storage_mm = 10.0 * root_depth_cm * theta_rz
    deficit_mm = 10.0 * root_depth_cm * max(0.0, theta_fc - theta_rz)
    return float(storage_mm), float(deficit_mm)
