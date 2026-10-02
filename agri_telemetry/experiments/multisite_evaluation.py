"""
Phase 5 Multi-Site Generalisation & External Validation Evaluator.
Executes rigorous out-of-site forecasting, uncertainty transfer, and advisory evaluation across independent USCRN stations.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import json
import numpy as np
import pandas as pd

from agri_telemetry.data.site_registry import (
    STATION_REGISTRY,
    StationMetadata,
    SiteSuitability,
    get_active_evaluation_sites,
    get_station_metadata,
)
from agri_telemetry.domain.enums import VariableName, DataClass
from agri_telemetry.ingestion.uscrn_parser import parse_uscrn_file
from agri_telemetry.ingestion.normalizer import normalize_uscrn_dataframe
from agri_telemetry.qc.engine import Tier1QCEngine
from agri_telemetry.state.soil_parameters import SoilProfileConfig
from agri_telemetry.state.state_builder import StateBuilder
from agri_telemetry.forecasting.persistence import PersistenceModel
from agri_telemetry.forecasting.statistical_ar import AutoregressiveForecaster
from agri_telemetry.forecasting.exogenous_model import EnvironmentalForecaster
from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator
from agri_telemetry.forecasting.uncertainty_calibration import (
    StaticQuantileCalibrator,
    RegimeConditionedCalibrator,
)
from agri_telemetry.decision.advisory_engine import OperationalAdvisoryEngine
from agri_telemetry.decision.water_risk import UncertaintyAwareRiskEvaluator, WaterRiskConfig
from agri_telemetry.decision.physical_deviation import PhysicalDeviationDetector, PhysicalDeviationConfig
from agri_telemetry.decision.persistence_filter import AlertPersistenceFilter, PersistenceFilterConfig


@dataclass
class SiteHorizonMetrics:
    horizon_hours: int
    test_samples: int
    b0_mae: float
    b0_rmse: float
    b0_mse: float
    b0_mbe: float
    m1_mae: float
    m1_rmse: float
    m1_mse: float
    m1_mae_skill: float
    m1_mse_skill: float
    m2_mae: float
    m2_rmse: float
    m2_mse: float
    m2_mae_skill: float
    m2_mse_skill: float
    hybrid_mae: float
    hybrid_rmse: float
    hybrid_mse: float
    hybrid_mae_skill: float
    hybrid_mse_skill: float
    u0_coverage_80: float
    u0_width_80: float
    u2_coverage_80: float
    u2_width_80: float
    u2_wet_coverage_80: float
    u2_dry_coverage_80: float


@dataclass
class SiteAdvisoryMetrics:
    total_records: int
    valid_states: int
    quarantined_records: int
    raw_alerts: int
    k2_alerts: int
    k3_alerts: int
    n_of_m_alerts: int
    critical_alerts: int
    warning_alerts: int
    episodes_g6h: int
    alert_hours: int
    compression_pct: float
    flutter_suppression_pct: float


@dataclass
class SingleSiteEvaluationResult:
    station_key: str
    station_id: str
    site_id: str
    station_name: str
    state: str
    climate_regime: str
    soil_texture: str
    annual_precip_mm: float
    test_start: str
    test_end: str
    total_samples: int
    test_samples: int
    horizon_metrics: Dict[int, SiteHorizonMetrics] = field(default_factory=dict)
    advisory_metrics: Optional[SiteAdvisoryMetrics] = None
    mean_mae_skill_1_48h: float = 0.0
    mean_hybrid_skill: float = 0.0
    generalisation_outcome: str = "SUPPORTED"
    failure_notes: List[str] = field(default_factory=list)


@dataclass
class MultiSiteEvaluationReport:
    generated_at: str
    baseline_station: str
    evaluated_stations: List[str]
    site_results: Dict[str, SingleSiteEvaluationResult] = field(default_factory=dict)
    cross_site_summary: Dict[str, Any] = field(default_factory=dict)

    def to_json(self, indent: int = 2) -> str:
        def custom_serializer(obj):
            if isinstance(obj, (SingleSiteEvaluationResult, SiteHorizonMetrics, SiteAdvisoryMetrics, MultiSiteEvaluationReport)):
                return asdict(obj)
            return str(obj)
        return json.dumps(asdict(self), default=custom_serializer, indent=indent)


class MultiSiteEvaluator:
    """
    Executes out-of-site validation across independent USCRN stations without future leakage.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        horizons: Optional[List[int]] = None,
        train_fraction: float = 0.50,
    ):
        self.data_dir = data_dir or (Path(__file__).parent.parent.parent / "data" / "uscrn")
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]
        self.train_fraction = train_fraction

    def evaluate_station(self, station_key: str) -> SingleSiteEvaluationResult:
        """Evaluates a single station by station key."""
        meta = get_station_metadata(station_key)
        if not meta:
            raise ValueError(f"Station '{station_key}' not found in registry.")

        file_path = self.data_dir / f"CRNH0203-2023-{station_key}.txt"
        if not file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path.resolve()}")

        # 1. Parse and normalize
        raw_df = parse_uscrn_file(file_path)
        events = normalize_uscrn_dataframe(raw_df, meta.station_id, meta.site_id)

        # 2. Tier 1 QC
        qc_engine = Tier1QCEngine()
        valid_events = []
        quarantined_count = 0
        for e in events:
            ev, is_q, _ = qc_engine.evaluate_event(e)
            if is_q:
                quarantined_count += 1
            else:
                valid_events.append(ev)

        # 3. State building with site-specific soil configuration
        soil_cfg = SoilProfileConfig(
            theta_fc=meta.default_fc,
            theta_wp=meta.default_wp,
            theta_sat=meta.default_sat,
        )
        builder = StateBuilder(soil_cfg)
        states = [builder.build_state(e) for e in valid_events]
        states = [s for s in states if s and s.is_valid]

        timestamps = [s.timestamp for s in states]
        theta_rz_series = [s.theta_rz for s in states]
        depletion_series = [s.depletion_fraction for s in states]

        # Chronological split
        split_idx = int(len(states) * self.train_fraction)
        train_timestamps = timestamps[:split_idx]
        train_theta = theta_rz_series[:split_idx]
        test_timestamps = timestamps[split_idx:]
        test_theta = theta_rz_series[split_idx:]

        # Meteorological feature alignment
        raw_indexed = raw_df.drop_duplicates(subset=["timestamp_utc"]).set_index("timestamp_utc")
        aligned_met = raw_indexed.reindex(timestamps).reset_index()
        train_met = aligned_met.iloc[:split_idx].reset_index(drop=True)
        test_met = aligned_met.iloc[split_idx:].reset_index(drop=True)

        # Fit models on TRAIN split ONLY
        # B0: Persistence
        b0_calibrator = EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        b0_calibrator.fit(train_theta)
        b0_model = PersistenceModel(horizons=self.horizons, calibrator=b0_calibrator)

        # M1: Autoregressive AR
        m1_model = AutoregressiveForecaster(horizons=self.horizons)
        m1_model.fit(train_timestamps, train_theta)

        # M2: Environmental ARX
        m2_model = EnvironmentalForecaster(horizons=self.horizons)
        m2_model.fit(train_timestamps, train_theta, train_met)

        # U0 & U2 Calibrators fit on train split residuals
        u0_calibrator = StaticQuantileCalibrator(horizons=self.horizons)
        u0_calibrator.fit(train_theta)

        u2_calibrator = RegimeConditionedCalibrator(horizons=self.horizons)
        u2_calibrator.fit(train_theta, train_met)

        # Extract test feature matrices
        X_test_m1, _ = m1_model.extractor.extract_features(test_timestamps, test_theta)
        X_test_m2, _ = m2_model.extractor.extract_features(test_timestamps, test_theta, met_df=test_met)

        horizon_metrics_dict: Dict[int, SiteHorizonMetrics] = {}
        skills_1_48 = []
        hybrid_skills_all = []
        failure_notes = []

        n_test = len(test_theta)
        p_series = test_met["precip_mm"].fillna(0.0).values
        p24_test = pd.Series(p_series).rolling(24, min_periods=1).sum().values
        solar_test = test_met["solar_rad_wm2"].fillna(0.0).values

        for h in self.horizons:
            if n_test <= h:
                continue

            actuals = np.array(test_theta[h:])
            n_eval = len(actuals)

            # B0 (Persistence)
            b0_p = np.array(test_theta[:-h])
            b0_err = actuals - b0_p
            b0_mae = float(np.mean(np.abs(b0_err)))
            b0_mse = float(np.mean(b0_err ** 2))
            b0_rmse = float(np.sqrt(b0_mse))
            b0_mbe = float(np.mean(b0_err))

            # M1 (Autoregressive)
            m1_raw = m1_model.predict_vectorized(X_test_m1, h)
            m1_p = m1_raw[:n_eval]
            m1_err = actuals - m1_p
            m1_mae = float(np.mean(np.abs(m1_err)))
            m1_mse = float(np.mean(m1_err ** 2))
            m1_rmse = float(np.sqrt(m1_mse))
            m1_mae_skill = float(1.0 - (m1_mae / b0_mae)) if b0_mae > 1e-7 else 0.0
            m1_mse_skill = float(1.0 - (m1_mse / b0_mse)) if b0_mse > 1e-10 else 0.0

            # M2 (Environmental ARX)
            m2_raw = m2_model.predict_vectorized(X_test_m2, h)
            m2_p = m2_raw[:n_eval]
            m2_err = actuals - m2_p
            m2_mae = float(np.mean(np.abs(m2_err)))
            m2_mse = float(np.mean(m2_err ** 2))
            m2_rmse = float(np.sqrt(m2_mse))
            m2_mae_skill = float(1.0 - (m2_mae / b0_mae)) if b0_mae > 1e-7 else 0.0
            m2_mse_skill = float(1.0 - (m2_mse / b0_mse)) if b0_mse > 1e-10 else 0.0

            # Hybrid strategy: M2 for 1-48h, M1 for 72-168h
            if h <= 48:
                hyb_mae = m2_mae
                hyb_mse = m2_mse
                hyb_rmse = m2_rmse
                hyb_mae_skill = m2_mae_skill
                hyb_mse_skill = m2_mse_skill
                skills_1_48.append(m2_mse_skill)
            else:
                hyb_mae = m1_mae
                hyb_mse = m1_mse
                hyb_rmse = m1_rmse
                hyb_mae_skill = m1_mae_skill
                hyb_mse_skill = m1_mse_skill

            hybrid_skills_all.append(hyb_mse_skill)

            # Uncertainty evaluation (U0 vs U2)
            u0_intervals = [
                u0_calibrator.predict_interval(
                    point_forecast=float(b0_p[i]),
                    horizon_hours=h,
                    nominal_coverage=0.80,
                )
                for i in range(n_eval)
            ]
            u0_lowers = np.array([iv.lower_bound for iv in u0_intervals])
            u0_uppers = np.array([iv.upper_bound for iv in u0_intervals])
            u0_cov = float(np.mean((actuals >= u0_lowers) & (actuals <= u0_uppers)))
            u0_width = float(np.mean(u0_uppers - u0_lowers))

            # U2 dynamic interval
            u2_intervals = [
                u2_calibrator.predict_interval(
                    point_forecast=float(m2_p[i] if h <= 48 else m1_p[i]),
                    horizon_hours=h,
                    precip_24h=float(p24_test[i]),
                    solar_rad=float(solar_test[i]),
                    nominal_coverage=0.80,
                )
                for i in range(n_eval)
            ]
            u2_lowers = np.array([iv.lower_bound for iv in u2_intervals])
            u2_uppers = np.array([iv.upper_bound for iv in u2_intervals])
            u2_cov = float(np.mean((actuals >= u2_lowers) & (actuals <= u2_uppers)))
            u2_width = float(np.mean(u2_uppers - u2_lowers))

            # Wet regime vs dry regime coverage
            is_wet = np.array([iv.regime_tag == "WET_ANTECEDENT" for iv in u2_intervals])
            wet_cov = float(np.mean((actuals[is_wet] >= u2_lowers[is_wet]) & (actuals[is_wet] <= u2_uppers[is_wet]))) if np.sum(is_wet) > 10 else u2_cov
            dry_cov = float(np.mean((actuals[~is_wet] >= u2_lowers[~is_wet]) & (actuals[~is_wet] <= u2_uppers[~is_wet]))) if np.sum(~is_wet) > 10 else u2_cov

            horizon_metrics_dict[h] = SiteHorizonMetrics(
                horizon_hours=h,
                test_samples=n_eval,
                b0_mae=b0_mae,
                b0_rmse=b0_rmse,
                b0_mse=b0_mse,
                b0_mbe=b0_mbe,
                m1_mae=m1_mae,
                m1_rmse=m1_rmse,
                m1_mse=m1_mse,
                m1_mae_skill=m1_mae_skill,
                m1_mse_skill=m1_mse_skill,
                m2_mae=m2_mae,
                m2_rmse=m2_rmse,
                m2_mse=m2_mse,
                m2_mae_skill=m2_mae_skill,
                m2_mse_skill=m2_mse_skill,
                hybrid_mae=hyb_mae,
                hybrid_rmse=hyb_rmse,
                hybrid_mse=hyb_mse,
                hybrid_mae_skill=hyb_mae_skill,
                hybrid_mse_skill=hyb_mse_skill,
                u0_coverage_80=u0_cov,
                u0_width_80=u0_width,
                u2_coverage_80=u2_cov,
                u2_width_80=u2_width,
                u2_wet_coverage_80=wet_cov,
                u2_dry_coverage_80=dry_cov,
            )

        # 4. Multi-Horizon Risk & Advisory Evaluation across the full year
        filter_raw = AlertPersistenceFilter(PersistenceFilterConfig(consecutive_steps=1))
        filter_k2 = AlertPersistenceFilter(PersistenceFilterConfig(mode="consecutive", consecutive_steps=2))
        filter_k3 = AlertPersistenceFilter(PersistenceFilterConfig(mode="consecutive", consecutive_steps=3))
        filter_nofm = AlertPersistenceFilter(PersistenceFilterConfig(mode="n_of_m", n_required=3, m_window=5))

        engine_raw = OperationalAdvisoryEngine(
            qc_engine=Tier1QCEngine(),
            deviation_detector=PhysicalDeviationDetector(),
            risk_evaluator=UncertaintyAwareRiskEvaluator(WaterRiskConfig(d_mad=0.50, critical_wilting_depletion=0.85)),
            persistence_filter=filter_raw,
            apply_persistence_filter=False,
        )

        raw_candidates_by_step: List[List[AlertEvent]] = []
        for evt in events:
            st = None
            if not (evt.qc_summary and evt.qc_summary.quarantined):
                st = builder.build_state(evt)
            res = engine_raw.process_cycle(event=evt, state=st)
            raw_candidates_by_step.append(res.raw_candidate_alerts)

        raw_alert_count = sum(len(c) for c in raw_candidates_by_step)
        k2_alert_count = sum(len(filter_k2.filter_alerts(c_list)) for c_list in raw_candidates_by_step)
        k3_alert_count = sum(len(filter_k3.filter_alerts(c_list)) for c_list in raw_candidates_by_step)
        nofm_alert_count = sum(len(filter_nofm.filter_alerts(c_list)) for c_list in raw_candidates_by_step)

        critical_count = sum(
            1 for c_list in raw_candidates_by_step for a in c_list if a.severity.value == "CRITICAL"
        )
        warning_count = sum(
            1 for c_list in raw_candidates_by_step for a in c_list if a.severity.value == "WARNING"
        )

        # Episode grouping (G=6h window)
        episodes_count = 0
        total_alert_hours = 0
        in_episode = False
        last_alert_time = None

        for evt, c_list in zip(events, raw_candidates_by_step):
            is_alert = len(c_list) > 0
            if is_alert:
                total_alert_hours += 1
                t_dt = datetime.fromisoformat(evt.event_time.replace("Z", "+00:00"))
                if not in_episode:
                    episodes_count += 1
                    in_episode = True
                elif last_alert_time and (t_dt - last_alert_time).total_seconds() > (6 * 3600):
                    episodes_count += 1
                last_alert_time = t_dt

        compression_pct = (1.0 - (episodes_count / raw_alert_count)) * 100 if raw_alert_count > 0 else 0.0
        flutter_suppression = ((raw_alert_count - k2_alert_count) / raw_alert_count) * 100 if raw_alert_count > 0 else 0.0

        advisory_metrics = SiteAdvisoryMetrics(
            total_records=len(raw_df),
            valid_states=len(states),
            quarantined_records=quarantined_count,
            raw_alerts=raw_alert_count,
            k2_alerts=k2_alert_count,
            k3_alerts=k3_alert_count,
            n_of_m_alerts=nofm_alert_count,
            critical_alerts=critical_count,
            warning_alerts=warning_count,
            episodes_g6h=episodes_count,
            alert_hours=total_alert_hours,
            compression_pct=compression_pct,
            flutter_suppression_pct=flutter_suppression,
        )

        mean_skill_1_48 = float(np.mean(skills_1_48)) if skills_1_48 else 0.0
        mean_hyb_skill = float(np.mean(hybrid_skills_all)) if hybrid_skills_all else 0.0

        # Determine generalisation outcome
        if mean_skill_1_48 > 0.02:
            outcome = "PARTIALLY_SUPPORTED"  # Short horizon positive skill; >48h requires NWP
        elif mean_skill_1_48 >= -0.05:
            outcome = "MARGINALLY_STABLE"
            failure_notes.append("In-situ past weather features provide marginal skill; strong persistence baseline.")
        else:
            outcome = "DEGRADED"
            failure_notes.append("Negative skill vs persistence; strong unobserved weather arrivals without forward NWP.")

        return SingleSiteEvaluationResult(
            station_key=station_key,
            station_id=meta.station_id,
            site_id=meta.site_id,
            station_name=meta.station_name,
            state=meta.state,
            climate_regime=meta.climate_regime.value,
            soil_texture=meta.soil_texture_class,
            annual_precip_mm=meta.annual_precip_mm_2023,
            test_start=test_timestamps[0].isoformat(),
            test_end=test_timestamps[-1].isoformat(),
            total_samples=len(states),
            test_samples=len(test_timestamps),
            horizon_metrics=horizon_metrics_dict,
            advisory_metrics=advisory_metrics,
            mean_mae_skill_1_48h=mean_skill_1_48,
            mean_hybrid_skill=mean_hyb_skill,
            generalisation_outcome=outcome,
            failure_notes=failure_notes,
        )

    def run_multi_site_benchmark(
        self,
        station_keys: Optional[List[str]] = None,
        save_report: bool = True,
    ) -> MultiSiteEvaluationReport:
        """Runs the benchmark across all target evaluation stations and produces report."""
        if not station_keys:
            station_keys = [
                "NE_Lincoln_11_SW", # Baseline reference
                "IL_Champaign_9_SW", # Midwest Corn Belt
                "NM_Las_Cruces_20_N", # Arid Southwest
                "GA_Watkinsville_5_SSE", # Subtropical Southeast
                "CO_Nunn_7_NNE", # Semi-Arid High Plains
                "SD_Sioux_Falls_14_NNE", # Northern Great Plains
            ]

        site_results: Dict[str, SingleSiteEvaluationResult] = {}
        for key in station_keys:
            print(f"[MultiSiteEvaluator] Evaluating station {key} ...")
            try:
                res = self.evaluate_station(key)
                site_results[key] = res
                print(f"  -> Done. 1-48h M2 Skill: {res.mean_mae_skill_1_48h*100:+.2f}%, Outcome: {res.generalisation_outcome}")
            except Exception as e:
                print(f"  -> Error evaluating {key}: {e}")

        # Compute cross-site summary statistics
        supported_count = sum(1 for r in site_results.values() if r.generalisation_outcome == "SUPPORTED")
        partial_count = sum(1 for r in site_results.values() if r.generalisation_outcome == "PARTIALLY_SUPPORTED")
        degraded_count = sum(1 for r in site_results.values() if r.generalisation_outcome == "DEGRADED")

        avg_m2_skill_1h = np.mean([r.horizon_metrics[1].m2_mse_skill for r in site_results.values() if 1 in r.horizon_metrics])
        avg_m2_skill_6h = np.mean([r.horizon_metrics[6].m2_mse_skill for r in site_results.values() if 6 in r.horizon_metrics])
        avg_m2_skill_24h = np.mean([r.horizon_metrics[24].m2_mse_skill for r in site_results.values() if 24 in r.horizon_metrics])
        avg_u2_cov_6h = np.mean([r.horizon_metrics[6].u2_coverage_80 for r in site_results.values() if 6 in r.horizon_metrics])
        avg_u0_cov_6h = np.mean([r.horizon_metrics[6].u0_coverage_80 for r in site_results.values() if 6 in r.horizon_metrics])

        cross_summary = {
            "total_sites_evaluated": len(site_results),
            "supported_count": supported_count,
            "partially_supported_count": partial_count,
            "degraded_count": degraded_count,
            "cross_site_avg_m2_skill_1h": float(avg_m2_skill_1h),
            "cross_site_avg_m2_skill_6h": float(avg_m2_skill_6h),
            "cross_site_avg_m2_skill_24h": float(avg_m2_skill_24h),
            "cross_site_avg_u2_cov_6h": float(avg_u2_cov_6h),
            "cross_site_avg_u0_cov_6h": float(avg_u0_cov_6h),
        }

        report = MultiSiteEvaluationReport(
            generated_at=datetime.utcnow().isoformat() + "Z",
            baseline_station="NE_Lincoln_11_SW",
            evaluated_stations=list(site_results.keys()),
            site_results=site_results,
            cross_site_summary=cross_summary,
        )

        if save_report:
            out_path = Path(__file__).parent.parent.parent / "runs" / "multisite_validation_report.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(report.to_json(), encoding="utf-8")
            print(f"[MultiSiteEvaluator] Report saved to {out_path.resolve()}")

        return report
