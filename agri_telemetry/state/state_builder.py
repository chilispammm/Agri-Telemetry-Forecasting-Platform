"""
Soil Water State Builder.
Constructs canonical SoilWaterState domain object from validated TelemetryEvents.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from agri_telemetry.contracts.telemetry_event import TelemetryEvent
from agri_telemetry.domain.enums import VariableName, QCFlag
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.state.soil_parameters import SoilProfileConfig
from agri_telemetry.state.depth_integration import integrate_root_zone_moisture
from agri_telemetry.state.depletion import (
    calculate_depletion_fraction,
    calculate_available_water_fraction,
    calculate_storage_and_deficit_mm,
)


class StateBuilder:
    """Builds SoilWaterState from validated TelemetryEvents."""

    def __init__(self, soil_config: Optional[SoilProfileConfig] = None):
        self.soil_config = soil_config or SoilProfileConfig()

    def build_state(self, event: TelemetryEvent) -> Optional[SoilWaterState]:
        """
        Constructs a SoilWaterState from a TelemetryEvent.
        Returns None if all root-zone moisture measurements are missing or quarantined.
        """
        # Extract VWC measurements by depth
        depth_vwc: Dict[float, Optional[float]] = {}
        for m in event.measurements:
            if m.variable_name == VariableName.VOLUMETRIC_WATER_CONTENT:
                if m.qc_flag == QCFlag.VALID and m.value is not None:
                    depth_vwc[m.depth_cm] = m.value
                else:
                    depth_vwc[m.depth_cm] = None

        theta_rz, weight_fraction, is_reliable = integrate_root_zone_moisture(
            depth_vwc=depth_vwc,
            weights=self.soil_config.layer_weights,
        )

        if theta_rz is None:
            return None

        event_dt = datetime.fromisoformat(event.event_time.replace("Z", "+00:00"))
        dr = calculate_depletion_fraction(theta_rz, self.soil_config.theta_fc, self.soil_config.theta_wp)
        faw = calculate_available_water_fraction(theta_rz, self.soil_config.theta_fc, self.soil_config.theta_wp)
        storage_mm, deficit_mm = calculate_storage_and_deficit_mm(
            theta_rz=theta_rz,
            theta_fc=self.soil_config.theta_fc,
            root_depth_cm=self.soil_config.root_depth_cm,
        )

        clean_depth_vwc = {d: v for d, v in depth_vwc.items() if v is not None}

        return SoilWaterState(
            timestamp=event_dt,
            site_id=event.site_id,
            source_id=event.source_id,
            depth_vwc=clean_depth_vwc,
            theta_rz=theta_rz,
            theta_fc=self.soil_config.theta_fc,
            theta_wp=self.soil_config.theta_wp,
            theta_sat=self.soil_config.theta_sat,
            depletion_fraction=dr,
            available_water_fraction=faw,
            root_depth_cm=self.soil_config.root_depth_cm,
            storage_mm=storage_mm,
            deficit_mm=deficit_mm,
            is_valid=is_reliable,
            metadata={
                "valid_weight_fraction": weight_fraction,
                "event_id": event.event_id,
                "data_class": event.provenance.data_class.value,
            },
        )
