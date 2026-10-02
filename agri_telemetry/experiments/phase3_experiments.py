"""
Phase 3 Formal Experiments Suite.
Executes EXP-20261002-007, EXP-20261002-008, and EXP-20261002-009.
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass
import pandas as pd
import numpy as np

from agri_telemetry.contracts.telemetry_event import TelemetryEvent
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.contracts.validator import assert_valid_payload
from agri_telemetry.domain.enums import AlertCategory, AlertSeverity, DataClass
from agri_telemetry.domain.models import SoilWaterState
from agri_telemetry.ingestion.uscrn_parser import parse_uscrn_file
from agri_telemetry.ingestion.normalizer import normalize_uscrn_dataframe
from agri_telemetry.qc.engine import Tier1QCEngine
from agri_telemetry.state.state_builder import StateBuilder
from agri_telemetry.state.soil_parameters import SoilProfileConfig
from agri_telemetry.decision.advisory_engine import OperationalAdvisoryEngine
from agri_telemetry.decision.water_risk import UncertaintyAwareRiskEvaluator, WaterRiskConfig
from agri_telemetry.decision.physical_deviation import PhysicalDeviationDetector, PhysicalDeviationConfig
from agri_telemetry.decision.persistence_filter import AlertPersistenceFilter, PersistenceFilterConfig
from agri_telemetry.simulation.scenario_runner import SyntheticScenarioRunner, ScenarioEvaluationResult
from agri_telemetry.simulation.scenarios import build_synthetic_scenarios


@dataclass
class Phase3ExperimentResults:
    """Comprehensive container for all Phase 3 experimental results."""
    # EXP-20261002-007 (Anomaly Taxonomy & Disambiguation)
    exp007_isolation_pass_rate: float
    exp007_taxonomy_accuracy: float
    exp007_total_cases_evaluated: int

    # EXP-20261002-008 (Alert Persistence & False-Alarm Reduction)
    exp008_raw_alerts_total: int
    exp008_k2_confirmed_alerts: int
    exp008_k2_suppression_pct: float
    exp008_k3_confirmed_alerts: int
    exp008_k3_suppression_pct: float
    exp008_nofm_confirmed_alerts: int
    exp008_nofm_suppression_pct: float

    # EXP-20261002-009 (Uncertainty-Aware Water Risk & Synthetic Benchmark)
    exp009_scenario_pass_count: int
    exp009_total_scenarios: int
    exp009_scenario_details: Dict[str, ScenarioEvaluationResult]
    exp009_historical_advisories_count: int
    exp009_schema_validation_pass_rate: float


class Phase3ExperimentRunner:
    """
    Orchestrates the formal execution of Phase 3 experiments.
    """

    def __init__(
        self,
        data_path: Optional[Path] = None,
        soil_config: Optional[SoilProfileConfig] = None,
    ):
        self.data_path = data_path or (
            Path(__file__).parent.parent.parent / "data" / "uscrn" / "CRNH0203-2023-NE_Lincoln_11_SW.txt"
        )
        self.soil_config = soil_config or SoilProfileConfig()

    def run_exp007_taxonomy_disambiguation(self) -> Dict[str, Any]:
        """
        EXP-20261002-007: Anomaly Taxonomy & Disambiguation Benchmark.
        Evaluates whether data-quality anomalies, physical deviations, and water risk are 100% disambiguated.
        """
        runner = SyntheticScenarioRunner(soil_config=self.soil_config)
        scenario_results = runner.run_all_scenarios()

        isolation_passed = all(res.isolation_preserved for res in scenario_results.values())
        target_detected_all = all(res.target_condition_detected for res in scenario_results.values())

        return {
            "isolation_pass_rate": 1.0 if isolation_passed else 0.0,
            "taxonomy_accuracy": 1.0 if target_detected_all else (sum(1 for r in scenario_results.values() if r.target_condition_detected) / len(scenario_results)),
            "total_cases_evaluated": len(scenario_results),
            "scenario_results": scenario_results,
        }

    def run_exp008_persistence_filtering(self) -> Dict[str, Any]:
        """
        EXP-20261002-008: Alert Persistence & False-Alarm Reduction Benchmark.
        Runs full 2023 hourly dataset (8,760 observations) under raw vs k=2 vs k=3 vs 3-of-5 filters.
        """
        df_raw = parse_uscrn_file(self.data_path)
        events = normalize_uscrn_dataframe(
            df_raw,
            source_id="USCRN_NE_Lincoln_11_SW",
            site_id="FIELD_LINCOLN_01",
            data_class=DataClass.OBSERVED,
        )

        state_builder = StateBuilder(soil_config=self.soil_config)

        # Filters under test
        filter_raw = AlertPersistenceFilter(PersistenceFilterConfig(consecutive_steps=1))
        filter_k2 = AlertPersistenceFilter(PersistenceFilterConfig(mode="consecutive", consecutive_steps=2))
        filter_k3 = AlertPersistenceFilter(PersistenceFilterConfig(mode="consecutive", consecutive_steps=3))
        filter_nofm = AlertPersistenceFilter(PersistenceFilterConfig(mode="n_of_m", n_required=3, m_window=5))

        # We will process telemetry events and collect raw candidates
        engine_raw = OperationalAdvisoryEngine(
            qc_engine=Tier1QCEngine(),
            deviation_detector=PhysicalDeviationDetector(),
            risk_evaluator=UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50)),
            persistence_filter=filter_raw,
            apply_persistence_filter=False,  # Emits raw candidates
        )

        raw_candidates_by_step: List[List[AlertEvent]] = []
        for evt in events:
            st = None
            if not (evt.qc_summary and evt.qc_summary.quarantined):
                st = state_builder.build_state(evt)
            res = engine_raw.process_cycle(event=evt, state=st)
            raw_candidates_by_step.append(res.raw_candidate_alerts)

        raw_total = sum(len(c) for c in raw_candidates_by_step)

        # Replay candidate stream through each persistence filter
        k2_emitted = 0
        k3_emitted = 0
        nofm_emitted = 0

        for c_list in raw_candidates_by_step:
            k2_alerts = filter_k2.filter_alerts(c_list)
            k3_alerts = filter_k3.filter_alerts(c_list)
            nofm_alerts = filter_nofm.filter_alerts(c_list)

            k2_emitted += len(k2_alerts)
            k3_emitted += len(k3_alerts)
            nofm_emitted += len(nofm_alerts)

        k2_suppr = ((raw_total - k2_emitted) / raw_total * 100.0) if raw_total > 0 else 0.0
        k3_suppr = ((raw_total - k3_emitted) / raw_total * 100.0) if raw_total > 0 else 0.0
        nofm_suppr = ((raw_total - nofm_emitted) / raw_total * 100.0) if raw_total > 0 else 0.0

        return {
            "raw_total": raw_total,
            "k2_emitted": k2_emitted,
            "k2_suppression_pct": k2_suppr,
            "k3_emitted": k3_emitted,
            "k3_suppression_pct": k3_suppr,
            "nofm_emitted": nofm_emitted,
            "nofm_suppression_pct": nofm_suppr,
        }

    def run_exp009_uncertainty_and_synthetic_suite(self) -> Dict[str, Any]:
        """
        EXP-20261002-009: Uncertainty-Aware Water Risk & Synthetic Suite Verification.
        """
        runner = SyntheticScenarioRunner(soil_config=self.soil_config)
        scenario_results = runner.run_all_scenarios()
        pass_count = sum(1 for r in scenario_results.values() if r.target_condition_detected and r.isolation_preserved)

        # Validate schema compliance on all generated alerts
        df_raw = parse_uscrn_file(self.data_path)
        events = normalize_uscrn_dataframe(
            df_raw,
            source_id="USCRN_NE_Lincoln_11_SW",
            site_id="FIELD_LINCOLN_01",
        )
        state_builder = StateBuilder(soil_config=self.soil_config)

        engine = OperationalAdvisoryEngine(
            qc_engine=Tier1QCEngine(),
            deviation_detector=PhysicalDeviationDetector(),
            risk_evaluator=UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50)),
            persistence_filter=AlertPersistenceFilter(PersistenceFilterConfig(consecutive_steps=2)),
            apply_persistence_filter=True,
        )

        all_emitted_advisories: List[AlertEvent] = []
        schema_valid_count = 0

        for evt in events:
            st = None
            if not (evt.qc_summary and evt.qc_summary.quarantined):
                st = state_builder.build_state(evt)
            res = engine.process_cycle(event=evt, state=st)
            for adv in res.confirmed_advisories:
                all_emitted_advisories.append(adv)
                try:
                    assert_valid_payload("alert", adv.to_dict())
                    schema_valid_count += 1
                except Exception:
                    pass

        schema_pass_rate = (schema_valid_count / len(all_emitted_advisories)) if all_emitted_advisories else 1.0

        return {
            "scenario_pass_count": pass_count,
            "total_scenarios": len(scenario_results),
            "scenario_results": scenario_results,
            "historical_advisories_count": len(all_emitted_advisories),
            "schema_pass_rate": schema_pass_rate,
        }

    def run_all(self) -> Phase3ExperimentResults:
        """Executes the full Phase 3 experiment suite."""
        res007 = self.run_exp007_taxonomy_disambiguation()
        res008 = self.run_exp008_persistence_filtering()
        res009 = self.run_exp009_uncertainty_and_synthetic_suite()

        return Phase3ExperimentResults(
            exp007_isolation_pass_rate=res007["isolation_pass_rate"],
            exp007_taxonomy_accuracy=res007["taxonomy_accuracy"],
            exp007_total_cases_evaluated=res007["total_cases_evaluated"],
            exp008_raw_alerts_total=res008["raw_total"],
            exp008_k2_confirmed_alerts=res008["k2_emitted"],
            exp008_k2_suppression_pct=res008["k2_suppression_pct"],
            exp008_k3_confirmed_alerts=res008["k3_emitted"],
            exp008_k3_suppression_pct=res008["k3_suppression_pct"],
            exp008_nofm_confirmed_alerts=res008["nofm_emitted"],
            exp008_nofm_suppression_pct=res008["nofm_suppression_pct"],
            exp009_scenario_pass_count=res009["scenario_pass_count"],
            exp009_total_scenarios=res009["total_scenarios"],
            exp009_scenario_details=res009["scenario_results"],
            exp009_historical_advisories_count=res009["historical_advisories_count"],
            exp009_schema_validation_pass_rate=res009["schema_pass_rate"],
        )
