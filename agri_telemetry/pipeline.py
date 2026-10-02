"""
Phase 1 Minimum Reproducible Vertical Slice Pipeline.
Executes the complete telemetry processing, forecasting, risk evaluation, and evidence persistence chain.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4
import numpy as np

from agri_telemetry.contracts.telemetry_event import TelemetryEvent
from agri_telemetry.contracts.forecast_event import ForecastEvent
from agri_telemetry.contracts.alert_event import AlertEvent
from agri_telemetry.domain.enums import TargetVariable, DataClass
from agri_telemetry.domain.models import SoilWaterState, RunSummary
from agri_telemetry.ingestion import (
    parse_uscrn_file,
    normalize_uscrn_dataframe,
    audit_uscrn_dataframe,
    IngestionAuditReport,
)
from agri_telemetry.qc import Tier1QCEngine, QuarantineBuffer
from agri_telemetry.state import SoilProfileConfig, StateBuilder
from agri_telemetry.forecasting import (
    EmpiricalUncertaintyCalibrator,
    PersistenceModel,
    WalkForwardEvaluator,
    ForecastingEngine,
    ForecastVerificationReport,
)
from agri_telemetry.alerts import RiskEvaluationConfig, AgronomicRiskEvaluator
from agri_telemetry.storage import SQLiteStore, EvidenceLedger


class Phase1Pipeline:
    """
    Executes Phase 1 Minimum Reproducible Vertical Slice.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        runs_dir: Optional[Path] = None,
        soil_config: Optional[SoilProfileConfig] = None,
        risk_config: Optional[RiskEvaluationConfig] = None,
        horizons: Optional[List[int]] = None,
    ):
        self.db_path = db_path or (Path(__file__).parent.parent / "data" / "agri_telemetry.db")
        self.runs_dir = runs_dir or (Path(__file__).parent.parent / "runs")
        self.soil_config = soil_config or SoilProfileConfig()
        self.risk_config = risk_config or RiskEvaluationConfig()
        self.horizons = horizons or [1, 6, 12, 24, 48, 72, 168]

        self.store = SQLiteStore(db_path=self.db_path)
        self.ledger = EvidenceLedger(runs_root=self.runs_dir)

    def run_on_dataset(
        self,
        data_file: Path,
        station_id: str = "USCRN_NE_Lincoln_11_SW",
        site_id: str = "FIELD_LINCOLN_01",
        dataset_name: str = "USCRN_CRNH0203_2023",
        max_records: Optional[int] = None,
        random_seed: int = 42,
    ) -> RunSummary:
        """
        Executes end-to-end reproducible processing on the specified real historical USCRN dataset.
        """
        run_id = f"RUN-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        now_exec = datetime.utcnow()

        # 1. Parse real raw historical data
        raw_df = parse_uscrn_file(data_file)
        if max_records:
            raw_df = raw_df.head(max_records)

        # 2. Ingestion Audit
        audit_report: IngestionAuditReport = audit_uscrn_dataframe(
            raw_df, dataset_name=dataset_name, station_id=station_id
        )

        # 3. Canonical Normalization
        events: List[TelemetryEvent] = normalize_uscrn_dataframe(
            raw_df,
            source_id=station_id,
            site_id=site_id,
            data_class=DataClass.OBSERVED,
            dataset_version=dataset_name,
        )

        # 4. Tier-1 Quality Control and Quarantine
        quarantine_buffer = QuarantineBuffer()
        qc_engine = Tier1QCEngine(quarantine_buffer=quarantine_buffer)

        evaluated_events: List[TelemetryEvent] = []
        qc_alerts: List[AlertEvent] = []
        for evt in events:
            ev_qc, is_q, qc_alert = qc_engine.evaluate_event(evt)
            evaluated_events.append(ev_qc)
            if qc_alert:
                qc_alerts.append(qc_alert)
            self.store.store_telemetry_event(ev_qc)
            if qc_alert:
                self.store.store_alert_event(qc_alert)

        # 5. State Construction
        state_builder = StateBuilder(soil_config=self.soil_config)
        valid_states: List[SoilWaterState] = []
        for evt in evaluated_events:
            # If quarantined, skip state construction for clean series
            if evt.qc_summary and evt.qc_summary.quarantined:
                continue
            st = state_builder.build_state(evt)
            if st and st.is_valid:
                valid_states.append(st)

        # 6. Chronological Walk-Forward Backtesting (50/50 Train-Test split)
        timestamps = [s.timestamp for s in valid_states]
        vwc_values = [s.theta_rz for s in valid_states]
        depletion_values = [s.depletion_fraction for s in valid_states]

        evaluator = WalkForwardEvaluator(horizons=self.horizons, train_fraction=0.50)
        verification_report = evaluator.evaluate(
            timestamps=timestamps,
            values=vwc_values,
            target_variable="volumetric_water_content",
        )

        # 7. Fit Uncertainty Calibrator on Calibration Split
        split_idx = int(len(valid_states) * 0.50)
        calibrator_vwc = EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        calibrator_vwc.fit(vwc_values[:split_idx])

        calibrator_depletion = EmpiricalUncertaintyCalibrator(horizons=self.horizons)
        calibrator_depletion.fit(depletion_values[:split_idx])

        # 8. Forecasting & Risk Evaluation Engine
        forecasting_engine = ForecastingEngine(calibrator=calibrator_vwc, horizons=self.horizons)
        risk_evaluator = AgronomicRiskEvaluator(config=self.risk_config, calibrator=calibrator_depletion)

        forecast_events_emitted: List[ForecastEvent] = []
        agronomic_alerts_emitted: List[AlertEvent] = []

        # Generate forecasts on the out-of-sample test split
        test_states = valid_states[split_idx:]
        for st in test_states:
            fc_event = forecasting_engine.generate_forecast(
                state=st,
                target_variable=TargetVariable.VOLUMETRIC_WATER_CONTENT,
                random_seed=random_seed,
            )
            forecast_events_emitted.append(fc_event)
            self.store.store_forecast_event(fc_event)

            # Evaluate Agronomic Risk
            risk_alerts = risk_evaluator.evaluate_state_and_forecast(
                state=st,
                forecast_horizons=self.horizons,
            )
            for ra in risk_alerts:
                agronomic_alerts_emitted.append(ra)
                self.store.store_alert_event(ra)

        # 9. Extract Metrics for Summary
        mae_dict = {h: m.mae for h, m in verification_report.horizon_metrics.items()}
        rmse_dict = {h: m.rmse for h, m in verification_report.horizon_metrics.items()}
        skill_dict = {h: m.skill_score_vs_mean for h, m in verification_report.horizon_metrics.items()}
        cov_dict = {h: m.coverage_80 for h, m in verification_report.horizon_metrics.items()}

        total_alerts_count = len(qc_alerts) + len(agronomic_alerts_emitted)

        summary = RunSummary(
            run_id=run_id,
            executed_at=now_exec,
            dataset_name=dataset_name,
            station_id=station_id,
            start_time=audit_report.start_time,
            end_time=audit_report.end_time,
            total_records=len(events),
            valid_events_count=len(valid_states),
            quarantined_events_count=quarantine_buffer.count(),
            forecast_events_count=len(forecast_events_emitted),
            alert_events_count=total_alerts_count,
            persistence_mae=mae_dict,
            persistence_rmse=rmse_dict,
            persistence_skill=skill_dict,
            interval_80_coverage=cov_dict,
            random_seed=random_seed,
            config={
                "d_mad": self.risk_config.d_mad,
                "tau_risk": self.risk_config.tau_risk,
                "theta_fc": self.soil_config.theta_fc,
                "theta_wp": self.soil_config.theta_wp,
                "horizons": self.horizons,
            },
        )

        # 10. Persist Summary in Store and Evidence Ledger
        self.store.store_run_summary(summary)
        self.ledger.record_run(summary)

        return summary


class OperationalPipeline:
    """
    Phase 4 Modular Operational Pipeline.
    Integrates validated forecasting, anomaly disambiguation, persistence filtering,
    structured observability, metrics collection, and MLOps experiment tracking.
    """

    def __init__(self, config: Optional[Any] = None):
        from agri_telemetry.config.settings import AppConfig, SoilConfig
        from agri_telemetry.observability.logging import setup_logger, trace_stage, set_run_id
        from agri_telemetry.observability.metrics import MetricsCollector, platform_metrics
        from agri_telemetry.mlops.experiment_tracker import ExperimentTracker
        from agri_telemetry.decision.advisory_engine import OperationalAdvisoryEngine
        from agri_telemetry.decision.persistence_filter import AlertPersistenceFilter, PersistenceFilterConfig
        from agri_telemetry.forecasting.persistence import PersistenceModel
        from agri_telemetry.forecasting.uncertainty import EmpiricalUncertaintyCalibrator

        self.config: AppConfig = config or AppConfig()
        self.logger = setup_logger(
            name="agri_telemetry.operational",
            level=self.config.observability.log_level,
            log_format=self.config.observability.log_format,
            service_name=self.config.observability.service_name,
            environment=self.config.observability.environment,
        )
        self.metrics: MetricsCollector = platform_metrics
        self.tracker = ExperimentTracker(
            runs_dir=self.config.storage.runs_dir,
            backend=self.config.mlops.tracking_backend,
            mlflow_uri=self.config.mlops.mlflow_tracking_uri,
        )

        db_path = Path(self.config.storage.db_path)
        runs_dir = Path(self.config.storage.runs_dir)
        self.store = SQLiteStore(db_path=db_path)
        self.ledger = EvidenceLedger(runs_root=runs_dir)

        # Scientific & Decision Engines
        soil_profile = SoilProfileConfig(
            theta_sat=self.config.soil.theta_sat,
            theta_fc=self.config.soil.theta_fc,
            theta_wp=self.config.soil.theta_wp,
            root_depth_cm=self.config.soil.root_zone_depth_cm,
        )
        self.state_builder = StateBuilder(soil_config=soil_profile)

        filter_mode = self.config.reliability.persistence_filter_mode
        p_config = PersistenceFilterConfig(
            mode="consecutive" if "CONSECUTIVE" in filter_mode else "n_of_m",
            consecutive_steps=2 if "2" in filter_mode else 3,
            n_required=3,
            m_window=5,
            pass_critical_immediately=True,
        )
        p_filter = AlertPersistenceFilter(config=p_config)
        self.advisory_engine = OperationalAdvisoryEngine(persistence_filter=p_filter)
        self.calibrator = EmpiricalUncertaintyCalibrator(horizons=self.config.forecasting.horizons)
        self.forecasting_engine = ForecastingEngine(calibrator=self.calibrator, horizons=self.config.forecasting.horizons)

    def run_on_dataset(
        self,
        data_file: Path | str,
        experiment_id: str = "EXP-PHASE4-OPERATIONAL",
        station_id: Optional[str] = None,
        site_id: Optional[str] = None,
        max_records: Optional[int] = None,
        random_seed: Optional[int] = None,
    ) -> RunSummary:
        """Executes full operational pipeline with observability, metrics, and MLOps tracking."""
        from agri_telemetry.observability.logging import trace_stage, set_run_id, set_correlation_id

        data_path = Path(data_file)
        seed = random_seed if random_seed is not None else self.config.forecasting.random_seed
        st_id = station_id or self.config.station_id
        si_id = site_id or self.config.site_id
        dataset_name = data_path.stem

        run_id = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        set_run_id(run_id)
        now_exec = datetime.now(timezone.utc)

        with self.tracker.start_run(
            run_id=run_id,
            experiment_id=experiment_id,
            dataset_name=dataset_name,
            station_id=st_id,
            site_id=si_id,
            random_seed=seed,
            horizons=self.config.forecasting.horizons,
            model_name="PERSISTENCE_CALIBRATED",
        ) as run_ctx:
            # 1. Parse Data
            with trace_stage("data_parsing", self.logger):
                raw_df = parse_uscrn_file(data_path)
                if max_records:
                    raw_df = raw_df.head(max_records)

            # 2. Ingestion Audit
            with trace_stage("data_audit", self.logger):
                audit_report = audit_uscrn_dataframe(raw_df, dataset_name=dataset_name, station_id=st_id)

            # 3. Normalization
            with trace_stage("normalization", self.logger):
                events = normalize_uscrn_dataframe(
                    raw_df,
                    source_id=st_id,
                    site_id=si_id,
                    data_class=DataClass.OBSERVED,
                    dataset_version=dataset_name,
                )

            # 4. Pipeline Execution
            quarantine_buffer = QuarantineBuffer()
            qc_engine = Tier1QCEngine(quarantine_buffer=quarantine_buffer)

            valid_states: List[SoilWaterState] = []
            qc_alerts: List[AlertEvent] = []
            evaluated_events: List[TelemetryEvent] = []

            with trace_stage("qc_and_state_construction", self.logger):
                for evt in events:
                    set_correlation_id(evt.event_id)
                    ev_qc, is_q, qc_alert = qc_engine.evaluate_event(evt)
                    evaluated_events.append(ev_qc)
                    self.store.store_telemetry_event(ev_qc)
                    self.metrics.record_ingested_event(valid=not is_q)

                    if qc_alert:
                        qc_alerts.append(qc_alert)
                        self.store.store_alert_event(qc_alert)
                        self.metrics.record_quarantine()

                    if not is_q:
                        st = self.state_builder.build_state(ev_qc)
                        if st and st.is_valid:
                            valid_states.append(st)

            # 5. Fit Calibrator on First 50%
            split_idx = int(len(valid_states) * 0.50)
            vwc_train = [s.theta_rz for s in valid_states[:split_idx]]
            self.calibrator.fit(vwc_train)

            # 6. Out-of-Sample Evaluation & Decision Cycle
            evaluator = WalkForwardEvaluator(horizons=self.config.forecasting.horizons, train_fraction=0.50)
            verification_report = evaluator.evaluate(
                timestamps=[s.timestamp for s in valid_states],
                values=[s.theta_rz for s in valid_states],
                target_variable="volumetric_water_content",
            )

            forecast_events: List[ForecastEvent] = []
            confirmed_advisories: List[AlertEvent] = []
            test_states = valid_states[split_idx:]

            with trace_stage("forecasting_and_decision", self.logger):
                for st in test_states:
                    fc_event = self.forecasting_engine.generate_forecast(
                        state=st,
                        target_variable=TargetVariable.VOLUMETRIC_WATER_CONTENT,
                        random_seed=seed,
                    )
                    forecast_events.append(fc_event)
                    self.store.store_forecast_event(fc_event)
                    self.metrics.record_forecast_emitted()

                    fc_dict = {
                        p.horizon_hours: {
                            "point_forecast": p.point_forecast,
                            "q10": p.quantiles.q10 if p.quantiles else p.point_forecast,
                            "q50": p.quantiles.q50 if p.quantiles else p.point_forecast,
                            "q90": p.quantiles.q90 if p.quantiles else p.point_forecast,
                            "width": (p.quantiles.q90 - p.quantiles.q10) if p.quantiles else 0.0,
                        }
                        for p in fc_event.predictions
                    }

                    # Operational Decision Cycle
                    dt_obj = st.timestamp if isinstance(st.timestamp, datetime) else datetime.fromisoformat(str(st.timestamp).replace("Z", "+00:00"))
                    ts_iso = dt_obj.isoformat()
                    matching_evt = next((e for e in evaluated_events if str(e.event_time).startswith(ts_iso[:19])), None)
                    if matching_evt:
                        cycle_res = self.advisory_engine.process_cycle(
                            event=matching_evt,
                            state=st,
                            forecast_predictions=fc_dict,
                        )
                        for adv in cycle_res.confirmed_advisories:
                            confirmed_advisories.append(adv)
                            self.store.store_alert_event(adv)
                            self.metrics.record_advisory_emitted(category=adv.category.value, severity=adv.severity.value)

            # 7. Metrics & MLOps Logging
            mae_dict = {h: m.mae for h, m in verification_report.horizon_metrics.items()}
            rmse_dict = {h: m.rmse for h, m in verification_report.horizon_metrics.items()}
            skill_dict = {h: m.skill_score_vs_mean for h, m in verification_report.horizon_metrics.items()}
            cov_dict = {h: m.coverage_80 for h, m in verification_report.horizon_metrics.items()}

            self.metrics.record_scientific_metrics(
                mae=mae_dict,
                rmse=rmse_dict,
                coverage=cov_dict,
                skill=skill_dict,
            )

            # Log to run context
            for h in self.config.forecasting.horizons:
                run_ctx.log_metric(f"mae_{h}h", mae_dict.get(h, 0.0))
                run_ctx.log_metric(f"rmse_{h}h", rmse_dict.get(h, 0.0))
                run_ctx.log_metric(f"coverage_80_{h}h", cov_dict.get(h, 0.0))
                run_ctx.log_metric(f"skill_vs_mean_{h}h", skill_dict.get(h, 0.0))

            run_ctx.log_metric("total_ingested", len(events))
            run_ctx.log_metric("total_quarantined", quarantine_buffer.count())
            run_ctx.log_metric("total_forecasts", len(forecast_events))
            run_ctx.log_metric("total_confirmed_advisories", len(confirmed_advisories))

            summary = RunSummary(
                run_id=run_id,
                executed_at=now_exec,
                dataset_name=dataset_name,
                station_id=st_id,
                start_time=audit_report.start_time,
                end_time=audit_report.end_time,
                total_records=len(events),
                valid_events_count=len(valid_states),
                quarantined_events_count=quarantine_buffer.count(),
                forecast_events_count=len(forecast_events),
                alert_events_count=len(qc_alerts) + len(confirmed_advisories),
                persistence_mae=mae_dict,
                persistence_rmse=rmse_dict,
                persistence_skill=skill_dict,
                interval_80_coverage=cov_dict,
                random_seed=seed,
                config=self.config.to_dict(),
            )

            self.store.store_run_summary(summary)
            self.ledger.record_run(summary)
            run_ctx.log_artifact(self.ledger.runs_root / run_id / "summary.json")

            return summary

    def close(self) -> None:
        """Closes storage and releases open file handles."""
        self.store.close()

