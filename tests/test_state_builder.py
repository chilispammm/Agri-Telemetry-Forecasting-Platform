"""
Unit & Integration Tests for Soil Water State Construction.
"""

from datetime import datetime, timezone
import pytest

from agri_telemetry.contracts import TelemetryEvent, TelemetryMeasurement
from agri_telemetry.domain.enums import VariableName, Unit, QCFlag
from agri_telemetry.state import (
    SoilProfileConfig,
    integrate_root_zone_moisture,
    calculate_depletion_fraction,
    calculate_available_water_fraction,
    calculate_storage_and_deficit_mm,
    StateBuilder,
)


def test_soil_profile_config():
    cfg = SoilProfileConfig(theta_fc=0.32, theta_wp=0.14, theta_sat=0.45, root_depth_cm=100.0)
    assert cfg.total_available_water_mm == pytest.approx(180.0, rel=1e-3)

    # Invalid: fc <= wp
    with pytest.raises(ValueError):
        SoilProfileConfig(theta_fc=0.10, theta_wp=0.15)


def test_depth_integration():
    weights = {5.0: 0.1, 10.0: 0.1, 20.0: 0.2, 50.0: 0.4, 100.0: 0.2}
    depth_vwc = {5.0: 0.30, 10.0: 0.30, 20.0: 0.25, 50.0: 0.20, 100.0: 0.15}
    
    # Complete layers
    theta_rz, weight_frac, reliable = integrate_root_zone_moisture(depth_vwc, weights)
    expected = 0.1*0.30 + 0.1*0.30 + 0.2*0.25 + 0.4*0.20 + 0.2*0.15  # 0.03+0.03+0.05+0.08+0.03 = 0.22
    assert theta_rz == pytest.approx(expected, rel=1e-4)
    assert weight_frac == pytest.approx(1.0, rel=1e-4)
    assert reliable is True

    # Missing 5cm layer -> re-weights remaining 90%
    depth_vwc_partial = {5.0: None, 10.0: 0.30, 20.0: 0.25, 50.0: 0.20, 100.0: 0.15}
    theta_rz_p, weight_frac_p, reliable_p = integrate_root_zone_moisture(depth_vwc_partial, weights)
    assert weight_frac_p == pytest.approx(0.9, rel=1e-4)
    assert reliable_p is True


def test_depletion_and_storage_metrics():
    fc = 0.32
    wp = 0.14

    # At FC -> Dr = 0.0, FAW = 1.0
    assert calculate_depletion_fraction(0.32, fc, wp) == pytest.approx(0.0, abs=1e-5)
    assert calculate_available_water_fraction(0.32, fc, wp) == pytest.approx(1.0, abs=1e-5)

    # At WP -> Dr = 1.0, FAW = 0.0
    assert calculate_depletion_fraction(0.14, fc, wp) == pytest.approx(1.0, abs=1e-5)
    assert calculate_available_water_fraction(0.14, fc, wp) == pytest.approx(0.0, abs=1e-5)

    # Midway -> theta = 0.23 -> Dr = (0.32 - 0.23)/0.18 = 0.09/0.18 = 0.50
    assert calculate_depletion_fraction(0.23, fc, wp) == pytest.approx(0.50, abs=1e-5)

    # Storage and deficit for 100cm root depth
    storage, deficit = calculate_storage_and_deficit_mm(0.23, fc, 100.0)
    assert storage == pytest.approx(230.0, abs=1e-3)
    assert deficit == pytest.approx(90.0, abs=1e-3)


def test_state_builder_from_telemetry_event():
    cfg = SoilProfileConfig(theta_fc=0.32, theta_wp=0.14)
    builder = StateBuilder(soil_config=cfg)

    now = datetime(2023, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    measurements = [
        TelemetryMeasurement(
            sensor_id=f"SOIL_VWC_{d}CM",
            variable_name=VariableName.VOLUMETRIC_WATER_CONTENT,
            depth_cm=float(d),
            value=0.25,
            unit=Unit.M3_M3,
            qc_flag=QCFlag.VALID,
        )
        for d in [5, 10, 20, 50, 100]
    ]

    event = TelemetryEvent.create_new(
        source_id="STATION_01",
        site_id="FIELD_01",
        event_time=now,
        measurements=measurements,
    )

    state = builder.build_state(event)
    assert state is not None
    assert state.theta_rz == pytest.approx(0.25, abs=1e-4)
    # Dr = (0.32 - 0.25)/0.18 = 0.07/0.18 = 0.3888
    assert state.depletion_fraction == pytest.approx(0.38888, rel=1e-3)
    assert state.is_valid is True
