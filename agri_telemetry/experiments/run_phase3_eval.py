"""
Execution script to generate full Phase 3 evidence numbers.
"""

import sys
from pathlib import Path

# Add project root to path
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from agri_telemetry.experiments.uncertainty_experiments import Phase3ExperimentRunner

def main():
    runner = Phase3ExperimentRunner()

    print("================================================================================")
    print("EXPERIMENT 1: HORIZON-PARTITIONED HYBRID FORECASTING BENCHMARK")
    print("================================================================================")
    part_res = runner.run_horizon_partitioned_evaluation()
    print("| Horizon | Assigned Model | MAE (Hybrid) | RMSE (Hybrid) | Bias MBE | RMSE (Persist) | Skill vs Persist | N Eval |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for h, m in part_res.metrics_by_horizon.items():
        model_name = m["assigned_model"]
        mae = m["mae_hybrid"]
        rmse = m["rmse_hybrid"]
        mbe = m["mbe_hybrid"]
        rmse_p = m["rmse_persist"]
        skill = m["skill_vs_persist"]
        n_eval = m["n_eval"]
        print(f"| `{h}h` | `{model_name}` | {mae:.4f} | {rmse:.4f} | {mbe:+.4f} | {rmse_p:.4f} | **{skill:+.4f}** ({skill*100:+.1f}%) | {n_eval} |")

    print("\n================================================================================")
    print("EXPERIMENT 2: FUTURE WEATHER / NWP VALUE INVESTIGATION (ORACLE ABLATION)")
    print("================================================================================")
    nwp_res = runner.run_future_weather_nwp_investigation()
    print("| Horizon | RMSE (Persist) | RMSE (Past ARX) | Skill (Past ARX) | RMSE (NWP Oracle) | Skill (NWP Oracle) | Skill Gain (NWP - Past) |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for h, m in nwp_res.metrics_by_horizon.items():
        rmse_p = m["rmse_persist"]
        rmse_past = m["rmse_past_arx"]
        skill_past = m["skill_past_arx"]
        rmse_ora = m["rmse_nwp_oracle"]
        skill_ora = m["skill_nwp_oracle"]
        gain = skill_ora - skill_past
        print(f"| `{h}h` | {rmse_p:.4f} | {rmse_past:.4f} | {skill_past:+.4f} | {rmse_ora:.4f} | **{skill_ora:+.4f}** | **{gain:+.4f}** ({gain*100:+.1f}%) |")

    print("\n================================================================================")
    print("EXPERIMENT 3: UNCERTAINTY CALIBRATION & DISPERSION SCALING BENCHMARK")
    print("================================================================================")
    unc_res = runner.run_uncertainty_benchmark(nominal_coverages=[0.80, 0.90])
    for nom in [0.80, 0.90]:
        print(f"\n--- NOMINAL COVERAGE: {nom*100:.0f}% ---")
        print("| Method | Horizon | Empirical Coverage (PICP) | Nominal | Mean Width (W) | Calibration Error |")
        print("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for method_name, metrics_list in unc_res.methods.items():
            for m in metrics_list:
                if m.nominal_coverage == nom:
                    err = m.empirical_coverage - m.nominal_coverage
                    print(f"| `{method_name}` | `{m.horizon_hours}h` | **{m.empirical_coverage*100:.1f}%** | {nom*100:.0f}% | {m.mean_interval_width:.4f} | {err*100:+.1f}% |")

    print("\n--- REGIME-PARTITIONED COVERAGE (NOMINAL 80%, U2 vs U0 at 6h, 24h, 168h) ---")
    for h in [6, 24, 168]:
        u0_m = next(m for m in unc_res.methods["U0_STATIC_QUANTILES"] if m.horizon_hours == h and m.nominal_coverage == 0.80)
        u2_m = next(m for m in unc_res.methods["U2_REGIME_CONDITIONED"] if m.horizon_hours == h and m.nominal_coverage == 0.80)
        print(f"\nHorizon {h}h:")
        for reg in ["WET_ANTECEDENT", "HIGH_EVAP", "DRY_QUIESCENT"]:
            u0_reg = u0_m.regime_breakdown.get(reg, {})
            u2_reg = u2_m.regime_breakdown.get(reg, {})
            n_s = u2_reg.get("n_samples", 0)
            cov_0 = u0_reg.get("coverage", 0.0) * 100
            w_0 = u0_reg.get("mean_width", 0.0)
            cov_2 = u2_reg.get("coverage", 0.0) * 100
            w_2 = u2_reg.get("mean_width", 0.0)
            print(f"  Regime {reg:15s} (n={n_s:4d}): U0 Coverage={cov_0:.1f}% (W={w_0:.4f}) vs U2 Coverage={cov_2:.1f}% (W={w_2:.4f})")

if __name__ == "__main__":
    main()
