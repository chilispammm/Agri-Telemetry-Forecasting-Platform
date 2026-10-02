"""
Phase 3 Operational Anomaly, Threshold & Advisory Intelligence Test Suite.
Verifies data quality isolation, physical deviation detection, uncertainty-aware risk,
persistence filtering, and JSON schema compliance.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
import pytest

from agri_telemetry.contracts.validator import assert_valid_payload
from agri_telemetry.contracts.telemetry_event import (
    TelemetryEvent,
    TelemetryMeasurement,
    TelemetryProvenance,
    QCSummary,
)
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.domain.enums import (
    AlertCategory,
    AlertSeverity,
    ThresholdType,
    DataClass,
    SyntheticFaultType,
    VariableName,
    Unit,
    QCFlag,
)
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.decision.taxonomy import (
    AnomalyClassification,
    PhysicalDeviationType,
    RiskCertaintyLevel,
    PersistenceStatus,
)
from agri_telemetry.decision.physical_deviation import (
    PhysicalDeviationDetector,
    PhysicalDeviationConfig,
)
from agri_telemetry.decision.water_risk import (
    UncertaintyAwareRiskEvaluator,
    WaterRiskConfig,
)
from agri_telemetry.decision.persistence_filter import (
    AlertPersistenceFilter,
    PersistenceFilterConfig,
)
from agri_telemetry.decision.advisory_engine import OperationalAdvisoryEngine
from agri_telemetry.simulation.scenario_runner import SyntheticScenarioRunner


def make_state(
    theta_rz: float = 0.26,
    depletion: float = 0.33,
    is_valid: bool = True,
    timestamp: Optional[datetime] = None,
) -> SoilWaterState:
    """Helper to create a mock SoilWaterState."""
    dt = timestamp or datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return SoilWaterState(
        timestamp=dt,
        site_id="FIELD_LINCOLN_01",
        source_id="USCRN_NE_Lincoln_11_SW",
        depth_vwc={5.0: theta_rz, 10.0: theta_rz, 20.0: theta_rz, 50.0: theta_rz, 100.0: theta_rz},
        theta_rz=theta_rz,
        theta_fc=0.32,
        theta_wp=0.14,
        theta_sat=0.45,
        depletion_fraction=depletion,
        available_water_fraction=1.0 - depletion,
        root_depth_cm=100.0,
        storage_mm=200.0,
        deficit_mm=80.0,
        is_valid=is_valid,
    )


def test_data_quality_isolation_prevents_agronomic_alert():
    """Verify that a data quality anomaly causes quarantine and NEVER emits agronomic alerts."""
    engine = OperationalAdvisoryEngine()

    now = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    # Non-physical value 1.95 m3/m3
    evt = TelemetryEvent(
        schema_version="1.0.0",
        event_id=str(uuid4()),
        source_id="USCRN_NE_Lincoln_11_SW",
        site_id="FIELD_LINCOLN_01",
        event_time=now.isoformat().replace("+00:00", "Z"),
        ingest_time=now.isoformat().replace("+00:00", "Z"),
        provenance=TelemetryProvenance(
            data_class=DataClass.SYNTHETIC_FAULT,
            network="USCRN",
            dataset_version="2023.v1",
        ),
        measurements=[
            TelemetryMeasurement(
                sensor_id="SOIL_VW_10CM",
                variable_name=VariableName.VOLUMETRIC_WATER_CONTENT,
                depth_cm=10.0,
                value=1.95,
                unit=Unit.M3_M3,
                qc_flag=QCFlag.VALID,
            )
        ],
    )

    state = make_state(depletion=0.95, is_valid=True)
    res = engine.process_cycle(event=evt, state=state)

    assert res.is_quarantined is True
    assert res.classification == AnomalyClassification.DATA_QUALITY_ANOMALY
    assert not any(a.category == AlertCategory.AGRONOMIC_RISK for a in res.confirmed_advisories)
    assert any(a.category == AlertCategory.DATA_QUALITY_ALERT for a in res.raw_candidate_alerts)


def test_physical_deviation_forecast_residual_breach():
    """Verify that 1-step forecast residual breach triggers Tier-2 PHYSICAL_DEVIATION alert."""
    detector = PhysicalDeviationDetector(PhysicalDeviationConfig(max_forecast_residual=0.020))
    # Expect 0.25, but state is 0.28 (residual 0.030 > 0.020)
    detector.record_prior_forecast(0.250)
    state = make_state(theta_rz=0.280)

    alerts = detector.evaluate(state)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.category == AlertCategory.PHYSICAL_DEVIATION
    assert a.trigger_condition.threshold_type == ThresholdType.MASS_BALANCE_RESIDUAL
    assert_valid_payload("alert", a.to_dict())


def test_physical_deviation_unphysical_drying_rate():
    """Verify that drying rate exceeding maximum ET limit triggers PHYSICAL_DEVIATION."""
    detector = PhysicalDeviationDetector(PhysicalDeviationConfig(max_hourly_drying_rate=0.025))

    t0 = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=1)

    s0 = make_state(theta_rz=0.280, timestamp=t0)
    s1 = make_state(theta_rz=0.240, timestamp=t1)  # Drop of 0.040 m3/m3/hr > 0.025

    detector.evaluate(s0)
    alerts = detector.evaluate(s1)

    assert len(alerts) == 1
    assert alerts[0].category == AlertCategory.PHYSICAL_DEVIATION
    assert "drying" in alerts[0].actionable_guidance.lower()


def test_physical_deviation_unexplained_wetting():
    """Verify that rapid wetting without precipitation triggers PHYSICAL_DEVIATION."""
    detector = PhysicalDeviationDetector(PhysicalDeviationConfig(min_unexplained_wetting_delta=0.015))
    detector.record_precipitation(0.0)

    t0 = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=1)

    s0 = make_state(theta_rz=0.200, timestamp=t0)
    s1 = make_state(theta_rz=0.225, timestamp=t1)  # Wetting of +0.025 with P=0.0

    detector.evaluate(s0)
    alerts = detector.evaluate(s1)

    assert len(alerts) == 1
    assert alerts[0].category == AlertCategory.PHYSICAL_DEVIATION
    assert "wetting" in alerts[0].actionable_guidance.lower()


def test_water_risk_mad_and_wilting_thresholds():
    """Verify that depletion >= MAD triggers WARNING, and depletion >= Wilting triggers CRITICAL."""
    evaluator = UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50, critical_wilting_depletion=0.85))

    s_mad = make_state(depletion=0.55)
    alerts_mad = evaluator.evaluate_state_and_forecast(s_mad)
    assert len(alerts_mad) == 1
    assert alerts_mad[0].severity == AlertSeverity.WARNING
    assert alerts_mad[0].trigger_condition.threshold_type == ThresholdType.MANAGEMENT_ALLOWABLE_DEPLETION

    s_wilt = make_state(depletion=0.90)
    alerts_wilt = evaluator.evaluate_state_and_forecast(s_wilt)
    assert len(alerts_wilt) == 1
    assert alerts_wilt[0].severity == AlertSeverity.CRITICAL
    assert alerts_wilt[0].trigger_condition.threshold_type == ThresholdType.CRITICAL_WILTING_PROXIMITY


def test_uncertainty_aware_risk_certainty_levels():
    """Verify classification of DEFINITELY_NOT_REACHED, PLAUSIBLY_REACHED, LIKELY_REACHED, and HIGHLY_UNCERTAIN."""
    evaluator = UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50, max_calibrated_horizon_hours=48))

    # 1. Definitely not reached
    c1 = evaluator.classify_forecast_risk_certainty(
        point_forecast=0.35, horizon_hours=24, interval_80=(0.30, 0.42)
    )
    assert c1 == RiskCertaintyLevel.DEFINITELY_NOT_REACHED

    # 2. Plausibly reached
    c2 = evaluator.classify_forecast_risk_certainty(
        point_forecast=0.46, horizon_hours=24, interval_80=(0.42, 0.54)
    )
    assert c2 == RiskCertaintyLevel.PLAUSIBLY_REACHED

    # 3. Likely reached
    c3 = evaluator.classify_forecast_risk_certainty(
        point_forecast=0.55, horizon_hours=24, interval_80=(0.50, 0.62)
    )
    assert c3 == RiskCertaintyLevel.LIKELY_REACHED

    # 4. Highly uncertain (>48h horizon)
    c4 = evaluator.classify_forecast_risk_certainty(
        point_forecast=0.48, horizon_hours=168, interval_80=(0.40, 0.60)
    )
    assert c4 == RiskCertaintyLevel.HIGHLY_UNCERTAIN


def test_alert_persistence_consecutive_filter():
    """Verify that single-observation transient alerts are suppressed and k-consecutive alerts are confirmed."""
    p_filter = AlertPersistenceFilter(PersistenceFilterConfig(consecutive_steps=2))

    t0 = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(hours=1)
    t2 = t1 + timedelta(hours=1)

    evaluator = UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50))
    s_alert = make_state(depletion=0.55, timestamp=t0)
    alerts_0 = evaluator.evaluate_state_and_forecast(s_alert)

    # Step 1: 1st trigger -> Pending confirmation -> 0 emitted
    out_0 = p_filter.filter_alerts(alerts_0)
    assert len(out_0) == 0
    assert p_filter.total_transient_suppressed == 1

    # Step 2: 2nd consecutive trigger -> Confirmed -> 1 emitted
    alerts_1 = evaluator.evaluate_state_and_forecast(make_state(depletion=0.56, timestamp=t1))
    out_1 = p_filter.filter_alerts(alerts_1)
    assert len(out_1) == 1
    assert "Confirmed: 2 consecutive steps" in out_1[0].actionable_guidance

    # Step 3: Condition clears -> no alert
    out_2 = p_filter.filter_alerts([])
    assert len(out_2) == 0


def test_alert_persistence_n_of_m_filter():
    """Verify N-of-M sliding window persistence filter."""
    p_filter = AlertPersistenceFilter(
        PersistenceFilterConfig(mode="n_of_m", n_required=3, m_window=5)
    )

    t0 = datetime(2023, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    evaluator = UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50))

    # Trigger at step 0 (1/1) -> suppressed
    a0 = evaluator.evaluate_state_and_forecast(make_state(depletion=0.55, timestamp=t0))
    assert len(p_filter.filter_alerts(a0)) == 0

    # Step 1: No trigger (1/2) -> suppressed
    assert len(p_filter.filter_alerts([])) == 0

    # Step 2: Trigger at step 2 (2/3) -> suppressed
    a2 = evaluator.evaluate_state_and_forecast(make_state(depletion=0.55, timestamp=t0 + timedelta(hours=2)))
    assert len(p_filter.filter_alerts(a2)) == 0

    # Step 3: Trigger at step 3 (3/4) -> CONFIRMED (3 in window of 4)
    a3 = evaluator.evaluate_state_and_forecast(make_state(depletion=0.55, timestamp=t0 + timedelta(hours=3)))
    out3 = p_filter.filter_alerts(a3)
    assert len(out3) == 1
    assert "Confirmed: 3/4 in window" in out3[0].actionable_guidance


def test_all_8_synthetic_scenarios_pass():
    """Verify that all 8 synthetic scenarios execute and satisfy isolation and detection criteria."""
    runner = SyntheticScenarioRunner()
    results = runner.run_all_scenarios()

    assert len(results) == 8
    for s_id, res in results.items():
        assert res.isolation_preserved is True, f"Scenario {s_id} failed isolation invariant"
        assert res.target_condition_detected is True, f"Scenario {s_id} failed target condition detection"
