"""
Audit Analysis Script for Phase 3 Advisory Decomposition & Episode Analysis.
"""

from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import numpy as np
from collections import Counter

from agri_telemetry.ingestion.uscrn_parser import parse_uscrn_file
from agri_telemetry.ingestion.normalizer import normalize_uscrn_dataframe
from agri_telemetry.state.state_builder import StateBuilder
from agri_telemetry.state.soil_parameters import SoilProfileConfig
from agri_telemetry.decision.advisory_engine import OperationalAdvisoryEngine
from agri_telemetry.decision.water_risk import UncertaintyAwareRiskEvaluator, WaterRiskConfig
from agri_telemetry.decision.physical_deviation import PhysicalDeviationDetector, PhysicalDeviationConfig
from agri_telemetry.decision.persistence_filter import AlertPersistenceFilter, PersistenceFilterConfig
from agri_telemetry.qc.engine import Tier1QCEngine


def main():
    data_path = Path("data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt")
    df_raw = parse_uscrn_file(data_path)
    events = normalize_uscrn_dataframe(df_raw, source_id="USCRN_NE_Lincoln_11_SW", site_id="FIELD_LINCOLN_01")

    state_builder = StateBuilder(soil_config=SoilProfileConfig())

    # Raw engine
    engine_raw = OperationalAdvisoryEngine(
        qc_engine=Tier1QCEngine(),
        deviation_detector=PhysicalDeviationDetector(),
        risk_evaluator=UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50)),
        persistence_filter=AlertPersistenceFilter(PersistenceFilterConfig(consecutive_steps=1)),
        apply_persistence_filter=False,
    )

    # Filtered engines
    engine_k2 = OperationalAdvisoryEngine(
        qc_engine=Tier1QCEngine(),
        deviation_detector=PhysicalDeviationDetector(),
        risk_evaluator=UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50)),
        persistence_filter=AlertPersistenceFilter(PersistenceFilterConfig(consecutive_steps=2)),
        apply_persistence_filter=True,
    )
    engine_k3 = OperationalAdvisoryEngine(
        qc_engine=Tier1QCEngine(),
        deviation_detector=PhysicalDeviationDetector(),
        risk_evaluator=UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50)),
        persistence_filter=AlertPersistenceFilter(PersistenceFilterConfig(consecutive_steps=3)),
        apply_persistence_filter=True,
    )
    engine_nofm = OperationalAdvisoryEngine(
        qc_engine=Tier1QCEngine(),
        deviation_detector=PhysicalDeviationDetector(),
        risk_evaluator=UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50)),
        persistence_filter=AlertPersistenceFilter(PersistenceFilterConfig(mode="n_of_m", n_required=3, m_window=5)),
        apply_persistence_filter=True,
    )

    records_k2 = []
    records_raw = []

    for idx, evt in enumerate(events):
        st = None
        if not (evt.qc_summary and evt.qc_summary.quarantined):
            st = state_builder.build_state(evt)

        # Raw cycle
        res_raw = engine_raw.process_cycle(event=evt, state=st)
        for a in res_raw.raw_candidate_alerts:
            records_raw.append({
                "idx": idx,
                "time": evt.event_time,
                "category": a.category.value,
                "severity": a.severity.value,
                "threshold_type": a.trigger_condition.threshold_type.value,
                "horizon": a.trigger_condition.forecast_horizon_hours,
            })

        # Confirmed k=2 cycle
        res_k2 = engine_k2.process_cycle(event=evt, state=st)
        for adv in res_k2.confirmed_advisories:
            records_k2.append({
                "idx": idx,
                "time": evt.event_time,
                "category": adv.category.value,
                "severity": adv.severity.value,
                "threshold_type": adv.trigger_condition.threshold_type.value,
                "horizon": adv.trigger_condition.forecast_horizon_hours,
                "depletion": st.depletion_fraction if st else None,
                "theta_rz": st.theta_rz if st else None,
                "is_quarantined": res_k2.is_quarantined,
            })

    df_raw_alerts = pd.DataFrame(records_raw)
    df_k2_alerts = pd.DataFrame(records_k2)

    print("=================================================================")
    print("PHASE 3 ADVISORY DECOMPOSITION AUDIT (2023 FULL YEAR, N=8,760h)")
    print("=================================================================")
    print(f"Total Raw Alerts Generated: {len(df_raw_alerts)}")
    print(f"Total Confirmed k=2 Advisories: {len(df_k2_alerts)}")

    print("\n--- 1. CATEGORY BREAKDOWN ---")
    print(df_k2_alerts["category"].value_counts().to_string())

    print("\n--- 2. SEVERITY BREAKDOWN ---")
    print(df_k2_alerts["severity"].value_counts().to_string())

    print("\n--- 3. TRIGGER TYPE BREAKDOWN ---")
    print(df_k2_alerts["threshold_type"].value_counts().to_string())

    print("\n--- 4. CATEGORY x SEVERITY CROSS-TABULATION ---")
    print(pd.crosstab(df_k2_alerts["category"], df_k2_alerts["severity"], margins=True).to_string())

    print("\n--- 5. TRIGGER TYPE x SEVERITY CROSS-TABULATION ---")
    print(pd.crosstab(df_k2_alerts["threshold_type"], df_k2_alerts["severity"], margins=True).to_string())

    print("\n--- 6. FORECAST HORIZON BREAKDOWN ---")
    print(df_k2_alerts["horizon"].fillna("Real-Time (0h)").value_counts().to_string())

    # Episode Grouping Function
    def calculate_episodes(df, max_gap_hours=6):
        episodes = []
        for (cat, thresh), group in df.groupby(["category", "threshold_type"]):
            group = group.sort_values("idx").copy()
            group["gap"] = group["idx"].diff()
            group["new_ep"] = (group["gap"] > max_gap_hours) | (group["gap"].isna())
            group["ep_id"] = group["new_ep"].cumsum()
            for ep_id, ep_df in group.groupby("ep_id"):
                episodes.append({
                    "category": cat,
                    "threshold_type": thresh,
                    "start_idx": ep_df["idx"].iloc[0],
                    "end_idx": ep_df["idx"].iloc[-1],
                    "start_time": ep_df["time"].iloc[0],
                    "end_time": ep_df["time"].iloc[-1],
                    "duration_hours": ep_df["idx"].iloc[-1] - ep_df["idx"].iloc[0] + 1,
                    "alert_count": len(ep_df),
                    "severities": list(ep_df["severity"].unique()),
                })
        return pd.DataFrame(episodes)

    df_ep_strict = calculate_episodes(df_k2_alerts, max_gap_hours=1)
    df_ep_6h = calculate_episodes(df_k2_alerts, max_gap_hours=6)

    print("\n=================================================================")
    print("EPISODE-LEVEL ALERT BURDEN ANALYSIS")
    print("=================================================================")
    print(f"Episode Grouping Rule (Strict Consecutive, max_gap=1h):")
    print(f"  Total Distinct Episodes: {len(df_ep_strict)}")
    print(f"  Mean Advisories per Episode: {df_ep_strict['alert_count'].mean():.1f}")
    print(f"  Median Advisories per Episode: {df_ep_strict['alert_count'].median():.1f}")
    print(f"  Max Advisories in Single Episode: {df_ep_strict['alert_count'].max()}")
    print(f"  Episode Deduplication Compression: {len(df_k2_alerts)} alerts -> {len(df_ep_strict)} episodes ({((len(df_k2_alerts)-len(df_ep_strict))/len(df_k2_alerts)*100.0):.2f}% reduction)")

    print(f"\nEpisode Grouping Rule (Tolerance Window, max_gap=6h):")
    print(f"  Total Distinct Episodes: {len(df_ep_6h)}")
    print(f"  Mean Advisories per Episode: {df_ep_6h['alert_count'].mean():.1f}")
    print(f"  Median Advisories per Episode: {df_ep_6h['alert_count'].median():.1f}")
    print(f"  Max Advisories in Single Episode: {df_ep_6h['alert_count'].max()}")
    print(f"  Episode Deduplication Compression: {len(df_k2_alerts)} alerts -> {len(df_ep_6h)} episodes ({((len(df_k2_alerts)-len(df_ep_6h))/len(df_k2_alerts)*100.0):.2f}% reduction)")

    print("\n--- Summary by Category (max_gap=6h) ---")
    for cat, grp in df_ep_6h.groupby("category"):
        print(f"  {cat}:")
        print(f"    Episodes: {len(grp)}")
        print(f"    Total Alerts: {grp['alert_count'].sum()}")
        print(f"    Mean Duration: {grp['duration_hours'].mean():.1f} hours ({grp['duration_hours'].mean()/24.0:.1f} days)")
        print(f"    Max Duration: {grp['duration_hours'].max()} hours ({grp['duration_hours'].max()/24.0:.1f} days)")

    print("\n--- Longest Underlying Risk Episodes (max_gap=6h) ---")
    top_ep = df_ep_6h.sort_values("duration_hours", ascending=False).head(8)
    for _, r in top_ep.iterrows():
        print(f"  * {r['category']} [{r['threshold_type']}]: {r['start_time']} -> {r['end_time']} ({r['duration_hours']}h / {r['duration_hours']/24.0:.1f} days, {r['alert_count']} alerts)")


if __name__ == "__main__":
    main()
