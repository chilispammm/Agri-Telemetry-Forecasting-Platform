"""
Synthetic Scenario Definitions for Phase 3 Intelligence Testing.
All scenarios are strictly labeled with SYNTHETIC provenance.
"""

from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from agri_telemetry.contracts.telemetry_event import (
    TelemetryEvent,
    TelemetryMeasurement,
    TelemetryProvenance,
    QCSummary,
)
from agri_telemetry.domain.enums import (
    DataClass,
    SyntheticFaultType,
    VariableName,
    Unit,
    QCFlag,
)


@dataclass
class ScenarioStep:
    """A single time-step inside a synthetic evaluation scenario."""
    timestamp: datetime
    measurements: Dict[str, Optional[float]]  # e.g. {"SOIL_VW_5CM": 0.22, "SOIL_VW_10CM": 0.22, ...}
    is_fault: bool = False
    fault_type: Optional[SyntheticFaultType] = None
    expected_quarantine: bool = False
    expected_alert_category: Optional[str] = None


@dataclass
class SyntheticScenario:
    """Complete specification of a controlled synthetic test scenario."""
    scenario_id: str
    name: str
    description: str
    total_steps: int
    steps: List[ScenarioStep]

    def to_telemetry_events(
        self,
        station_id: str = "USCRN_NE_Lincoln_11_SW",
        site_id: str = "FIELD_LINCOLN_01",
    ) -> List[TelemetryEvent]:
        """Converts scenario steps into validated TelemetryEvent payloads."""
        events: List[TelemetryEvent] = []

        for s in self.steps:
            meas_list: List[TelemetryMeasurement] = []
            flag_count = 0
            is_quarantined = s.expected_quarantine

            for sensor_name, val in s.measurements.items():
                if "VW" in sensor_name:
                    var_name = VariableName.VOLUMETRIC_WATER_CONTENT
                    unit = Unit.M3_M3
                    if "5CM" in sensor_name:
                        depth = 5.0
                    elif "10CM" in sensor_name:
                        depth = 10.0
                    elif "20CM" in sensor_name:
                        depth = 20.0
                    elif "50CM" in sensor_name:
                        depth = 50.0
                    elif "100CM" in sensor_name:
                        depth = 100.0
                    else:
                        depth = 10.0
                elif "P_" in sensor_name:
                    var_name = VariableName.PRECIPITATION
                    unit = Unit.MM
                    depth = 0.0
                elif "TEMP" in sensor_name:
                    var_name = VariableName.AIR_TEMPERATURE
                    unit = Unit.DEGC
                    depth = 0.0
                else:
                    var_name = VariableName.VOLUMETRIC_WATER_CONTENT
                    unit = Unit.M3_M3
                    depth = 10.0

                qc_flag = QCFlag.VALID
                if s.is_fault:
                    qc_flag = QCFlag.SYNTHETIC_CORRUPTED if val is not None else QCFlag.MISSING
                    flag_count += 1

                meas_list.append(
                    TelemetryMeasurement(
                        sensor_id=sensor_name,
                        variable_name=var_name,
                        depth_cm=depth,
                        value=val,
                        unit=unit,
                        qc_flag=qc_flag,
                    )
                )

            data_class = DataClass.SYNTHETIC_FAULT if s.is_fault else DataClass.SIMULATED_REPLAY
            prov = TelemetryProvenance(
                data_class=data_class,
                network="USCRN_SYNTHETIC_SUITE",
                dataset_version="PHASE3_BENCHMARK_v1",
                synthetic_fault_type=s.fault_type,
            )

            evt = TelemetryEvent(
                schema_version="1.0.0",
                event_id=str(uuid4()),
                source_id=station_id,
                site_id=site_id,
                event_time=s.timestamp.isoformat().replace("+00:00", "Z"),
                ingest_time=s.timestamp.isoformat().replace("+00:00", "Z"),
                provenance=prov,
                measurements=meas_list,
                qc_summary=QCSummary(
                    all_valid=(flag_count == 0),
                    flag_count=flag_count,
                    quarantined=is_quarantined,
                ),
            )
            events.append(evt)

        return events


def _make_profile(vwc: Optional[float], precip: float = 0.0) -> Dict[str, Optional[float]]:
    """Helper to generate full 5-depth profile measurements."""
    return {
        "SOIL_VW_5CM": vwc,
        "SOIL_VW_10CM": vwc,
        "SOIL_VW_20CM": vwc,
        "SOIL_VW_50CM": vwc,
        "SOIL_VW_100CM": vwc,
        "P_OFFICIAL": precip,
    }


def build_synthetic_scenarios() -> Dict[str, SyntheticScenario]:
    """Generates the 8 canonical Phase 3 test scenarios."""
    scenarios: Dict[str, SyntheticScenario] = {}
    base_time = datetime(2023, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

    # 1. SCENARIO_1_SENSOR_SPIKE: Single-hour transient excursion (+0.29 m3/m3)
    steps_1: List[ScenarioStep] = []
    for h in range(12):
        t = base_time + timedelta(hours=h)
        is_spike = (h == 5)
        vwc = 0.55 if is_spike else 0.26
        steps_1.append(
            ScenarioStep(
                timestamp=t,
                measurements=_make_profile(vwc),
                is_fault=is_spike,
                fault_type=SyntheticFaultType.VALUE_SPIKE if is_spike else None,
                expected_quarantine=is_spike,
                expected_alert_category="DATA_QUALITY_ALERT" if is_spike else None,
            )
        )
    scenarios["SCENARIO_1_SENSOR_SPIKE"] = SyntheticScenario(
        scenario_id="SCENARIO_1_SENSOR_SPIKE",
        name="Transient Sensor Spike",
        description="Single-hour isolated +0.29 m3/m3 spike without rain. Quarantined in Tier 1; 0 agronomic alerts leaked.",
        total_steps=len(steps_1),
        steps=steps_1,
    )

    # 2. SCENARIO_2_STUCK_SENSOR: Frozen sensor flatline for 18h
    steps_2: List[ScenarioStep] = []
    for h in range(18):
        t = base_time + timedelta(hours=h)
        # Identical float value for 18h at 0.26
        steps_2.append(
            ScenarioStep(
                timestamp=t,
                measurements=_make_profile(0.2615),
                is_fault=(h >= 12),
                fault_type=SyntheticFaultType.SENSOR_STUCK if (h >= 12) else None,
                expected_quarantine=(h >= 12),
                expected_alert_category="DATA_QUALITY_ALERT" if (h >= 12) else None,
            )
        )
    scenarios["SCENARIO_2_STUCK_SENSOR"] = SyntheticScenario(
        scenario_id="SCENARIO_2_STUCK_SENSOR",
        name="Stuck Sensor Flatline",
        description="18 hours of frozen sensor reading. Tier-1 stuck rule triggers after 12h and quarantines series.",
        total_steps=len(steps_2),
        steps=steps_2,
    )

    # 3. SCENARIO_3_SENSOR_DROPOUT: Missingness for 6h
    steps_3: List[ScenarioStep] = []
    for h in range(12):
        t = base_time + timedelta(hours=h)
        is_missing = (3 <= h < 9)
        val = None if is_missing else 0.24
        steps_3.append(
            ScenarioStep(
                timestamp=t,
                measurements=_make_profile(val),
                is_fault=is_missing,
                fault_type=SyntheticFaultType.PACKET_DROP if is_missing else None,
                expected_quarantine=False,
            )
        )
    scenarios["SCENARIO_3_SENSOR_DROPOUT"] = SyntheticScenario(
        scenario_id="SCENARIO_3_SENSOR_DROPOUT",
        name="Sensor Packet Dropout",
        description="6-hour telemetry dropout. Handled gracefully without crashes or false alarms.",
        total_steps=len(steps_3),
        steps=steps_3,
    )

    # 4. SCENARIO_4_UNPHYSICAL_DRYING: Abnormal rapid drying without drainage
    steps_4: List[ScenarioStep] = []
    current_val = 0.28
    for h in range(10):
        t = base_time + timedelta(hours=h)
        if h == 4:
            current_val -= 0.06  # Step drop of 0.06 m3/m3 in 1 hour
        else:
            current_val -= 0.001
        steps_4.append(
            ScenarioStep(
                timestamp=t,
                measurements=_make_profile(current_val),
                is_fault=False,
                expected_alert_category="PHYSICAL_DEVIATION" if (h == 4) else None,
            )
        )
    scenarios["SCENARIO_4_UNPHYSICAL_DRYING"] = SyntheticScenario(
        scenario_id="SCENARIO_4_UNPHYSICAL_DRYING",
        name="Unphysical Soil Drying Rate",
        description="Sudden drop of 0.06 m3/m3/hr. Detected as Tier-2 PHYSICAL_DEVIATION.",
        total_steps=len(steps_4),
        steps=steps_4,
    )

    # 5. SCENARIO_5_UNEXPLAINED_INFILTRATION: Wetting without precipitation
    steps_5: List[ScenarioStep] = []
    curr_v = 0.18
    for h in range(10):
        t = base_time + timedelta(hours=h)
        if h == 4:
            curr_v += 0.035  # Wetting jump of +0.035 m3/m3 with P = 0.0 mm
        steps_5.append(
            ScenarioStep(
                timestamp=t,
                measurements=_make_profile(curr_v, precip=0.0),
                is_fault=False,
                expected_alert_category="PHYSICAL_DEVIATION" if (h == 4) else None,
            )
        )
    scenarios["SCENARIO_5_UNEXPLAINED_INFILTRATION"] = SyntheticScenario(
        scenario_id="SCENARIO_5_UNEXPLAINED_INFILTRATION",
        name="Unexplained Infiltration",
        description="Rapid wetting +0.035 m3/m3/hr with P=0.0mm rain. Detected as Tier-2 PHYSICAL_DEVIATION.",
        total_steps=len(steps_5),
        steps=steps_5,
    )

    # 6. SCENARIO_6_APPROACHING_MAD: Drying trajectory approaching MAD (0.50)
    steps_6: List[ScenarioStep] = []
    # Start at theta_rz = 0.235 (depletion ~ 0.47)
    curr_th = 0.236
    for h in range(12):
        t = base_time + timedelta(hours=h)
        curr_th -= 0.001
        steps_6.append(
            ScenarioStep(
                timestamp=t,
                measurements=_make_profile(curr_th),
                is_fault=False,
                expected_alert_category="AGRONOMIC_RISK" if (h >= 6) else None,
            )
        )
    scenarios["SCENARIO_6_APPROACHING_MAD"] = SyntheticScenario(
        scenario_id="SCENARIO_6_APPROACHING_MAD",
        name="Approaching MAD Threshold",
        description="Soil moisture approaches MAD. Monitored for early risk advisory.",
        total_steps=len(steps_6),
        steps=steps_6,
    )

    # 7. SCENARIO_7_PERSISTENT_DROUGHT_MAD_CROSSING: Sustained drought crossing MAD to Wilting
    steps_7: List[ScenarioStep] = []
    # Soil drying from theta_rz = 0.22 (depletion 0.55) down to 0.15 (depletion 0.94)
    th_drought = 0.22
    for h in range(24):
        t = base_time + timedelta(hours=h)
        if h > 0 and h % 2 == 0:
            th_drought -= 0.006
        steps_7.append(
            ScenarioStep(
                timestamp=t,
                measurements=_make_profile(th_drought),
                is_fault=False,
                expected_alert_category="AGRONOMIC_RISK",
            )
        )
    scenarios["SCENARIO_7_PERSISTENT_DROUGHT_MAD_CROSSING"] = SyntheticScenario(
        scenario_id="SCENARIO_7_PERSISTENT_DROUGHT_MAD_CROSSING",
        name="Persistent Drought & Wilting Proximity",
        description="Sustained drought crossing MAD (0.50) and reaching Wilting Proximity (0.85). Emits confirmed WARNING and CRITICAL advisories.",
        total_steps=len(steps_7),
        steps=steps_7,
    )

    # 8. SCENARIO_8_AMBIGUOUS_UNCERTAIN_CROSSING: Hovering at boundary with noise
    steps_8: List[ScenarioStep] = []
    # Depletion oscillates: theta_fc=0.32, theta_wp=0.14 -> theta_MAD(0.50)=0.230
    # Alternates between 0.232 (depletion=0.488, no alert) and 0.228 (depletion=0.511, MAD alert)
    for h in range(12):
        t = base_time + timedelta(hours=h)
        th_val = 0.232 if (h % 2 == 0) else 0.228
        steps_8.append(
            ScenarioStep(
                timestamp=t,
                measurements=_make_profile(th_val),
                is_fault=False,
            )
        )
    scenarios["SCENARIO_8_AMBIGUOUS_UNCERTAIN_CROSSING"] = SyntheticScenario(
        scenario_id="SCENARIO_8_AMBIGUOUS_UNCERTAIN_CROSSING",
        name="Ambiguous / Fluttering Threshold Boundary",
        description="Depletion oscillates across MAD boundary. Persistence filter suppresses alert flapping.",
        total_steps=len(steps_8),
        steps=steps_8,
    )

    return scenarios
