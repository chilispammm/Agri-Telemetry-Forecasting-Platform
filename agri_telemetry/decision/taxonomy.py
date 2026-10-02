"""
Phase 3 Operational Anomaly & Risk Taxonomy.
Strictly distinguishes Data Quality, Physical Deviations, and Agronomic Threshold Risks.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


class AnomalyClassification(str, Enum):
    """Canonical classification for all platform observations and alerts."""
    DATA_QUALITY_ANOMALY = "DATA_QUALITY_ANOMALY"      # Tier 1: Hardware / communication / format faults
    PHYSICAL_DEVIATION = "PHYSICAL_DEVIATION"          # Tier 2: Real-world hydrological / thermodynamic anomalies
    OPERATIONAL_WATER_RISK = "OPERATIONAL_WATER_RISK"  # Tier 3: Agronomic threshold exceedances (MAD, Wilting)
    NORMAL_OPERATION = "NORMAL_OPERATION"              # Nominal expected state


class PhysicalDeviationType(str, Enum):
    """Types of physical / hydrological deviations from expected behavior."""
    FORECAST_RESIDUAL_BREACH = "FORECAST_RESIDUAL_BREACH"      # |y_t - y_hat_{t|t-1}| > threshold
    UNPHYSICAL_DRYING_RATE = "UNPHYSICAL_DRYING_RATE"          # dtheta/dt exceeds maximum ET/drainage limit
    UNEXPLAINED_INFILTRATION = "UNEXPLAINED_INFILTRATION"      # Significant wetting without recorded precipitation
    HYDRAULIC_INVERSION = "HYDRAULIC_INVERSION"                # Deep layer wetting before shallow layer


class RiskCertaintyLevel(str, Enum):
    """Uncertainty-aware threshold crossing classification."""
    DEFINITELY_NOT_REACHED = "DEFINITELY_NOT_REACHED"  # Upper quantile q90 < threshold
    PLAUSIBLY_REACHED = "PLAUSIBLY_REACHED"            # Median q50 < threshold <= q90
    LIKELY_REACHED = "LIKELY_REACHED"                  # Median q50 >= threshold
    HIGHLY_UNCERTAIN = "HIGHLY_UNCERTAIN"              # Interval spans threshold but interval width is excessive (>48h in-situ)


class PersistenceStatus(str, Enum):
    """State of an alert candidate under persistence filtering."""
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"  # Detected, accumulating confirmation steps
    CONFIRMED = "CONFIRMED"                        # Persistence threshold satisfied, active advisory emitted
    RESOLVED = "RESOLVED"                          # Condition returned to normal


@dataclass
class AnomalyAssessment:
    """Detailed explainable assessment output from the decision layer."""
    classification: AnomalyClassification
    primary_reason: str
    is_quarantined: bool
    requires_operator_review: bool
    deviation_type: Optional[PhysicalDeviationType] = None
    risk_certainty: Optional[RiskCertaintyLevel] = None
    details: Optional[Dict[str, Any]] = None
