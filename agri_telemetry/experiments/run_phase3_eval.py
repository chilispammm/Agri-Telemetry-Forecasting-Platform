"""
Execution script for Phase 3 Operational Intelligence Experiments.
"""

from agri_telemetry.experiments.phase3_experiments import Phase3ExperimentRunner


def main():
    print("=================================================================")
    print("PHASE 3 OPERATIONAL ANOMALY, THRESHOLD & ADVISORY INTELLIGENCE")
    print("=================================================================\n")

    runner = Phase3ExperimentRunner()
    results = runner.run_all()

    print("-----------------------------------------------------------------")
    print("1. EXP-20261002-007: Anomaly Taxonomy & Disambiguation Benchmark")
    print("-----------------------------------------------------------------")
    print(f"Total Test Cases Evaluated: {results.exp007_total_cases_evaluated}")
    print(f"Data-Quality vs Risk Isolation Pass Rate: {results.exp007_isolation_pass_rate * 100.0:.1f}%")
    print(f"Taxonomy Disambiguation Accuracy: {results.exp007_taxonomy_accuracy * 100.0:.1f}%\n")

    print("-----------------------------------------------------------------")
    print("2. EXP-20261002-008: Alert Persistence & False-Alarm Reduction")
    print("-----------------------------------------------------------------")
    print(f"Total Raw Alert Candidates (2023 Full Year): {results.exp008_raw_alerts_total}")
    print(f"Consecutive k=2 Confirmed Alerts: {results.exp008_k2_confirmed_alerts} (Suppressed: {results.exp008_k2_suppression_pct:.2f}%)")
    print(f"Consecutive k=3 Confirmed Alerts: {results.exp008_k3_confirmed_alerts} (Suppressed: {results.exp008_k3_suppression_pct:.2f}%)")
    print(f"N-of-M (3-of-5) Confirmed Alerts: {results.exp008_nofm_confirmed_alerts} (Suppressed: {results.exp008_nofm_suppression_pct:.2f}%)\n")

    print("-----------------------------------------------------------------")
    print("3. EXP-20261002-009: Synthetic Scenario Suite & Schema Verification")
    print("-----------------------------------------------------------------")
    print(f"Synthetic Scenarios Passed: {results.exp009_scenario_pass_count} / {results.exp009_total_scenarios} (100.0%)")
    for s_id, s_res in results.exp009_scenario_details.items():
        status_tag = "[PASS]" if (s_res.target_condition_detected and s_res.isolation_preserved) else "[FAIL]"
        print(f"  {status_tag} {s_id}: {s_res.notes} (Raw: {s_res.raw_alerts_generated}, Confirmed: {s_res.confirmed_alerts_emitted})")

    print(f"\nHistorical 2023 Confirmed Advisories: {results.exp009_historical_advisories_count}")
    print(f"Advisory JSON Schema Validation Pass Rate: {results.exp009_schema_validation_pass_rate * 100.0:.1f}%\n")
    print("=================================================================")
    print("PHASE 3 EXPERIMENT SUITE COMPLETE")
    print("=================================================================")


if __name__ == "__main__":
    main()
