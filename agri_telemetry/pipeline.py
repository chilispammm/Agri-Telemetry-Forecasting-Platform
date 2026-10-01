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
