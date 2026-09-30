# Agri Telemetry & Forecasting Platform — Implementation Plan

**Status:** DECIDED  
**Last Updated:** September 30, 2026  
**Document:** `08_implementation/IMPLEMENTATION_PLAN.md` / `10. Implementation Plan/Implementation Plan - Agri Telemetry & Forecasting Platform.md`

---

## 1. Plan Purpose & Execution Philosophy

This document outlines the concrete, execution-oriented roadmap for building the **Agri Telemetry & Forecasting Platform**. 

In strict adherence to **Rule #18** (*"Keep the simplest architecture that satisfies demonstrated requirements"*) and **Rule #29** (*"Do not optimise for impressive architecture. Optimise for evidence, reproducibility, and demonstrated decision value"*), this plan focuses on delivering a verified, leak-free **Minimum Reproducible Vertical Slice** first, before introducing any optional infrastructure.

---

## 2. Phased Build Scope

```mermaid
flowchart TD
    subgraph Phase 1: MUST BUILD NOW
        A1[Historical Station Ingestion & Clean Data Pipeline] --> A2[Event Validation & Synthetic Fault Injector]
        A2 --> A3[State Estimation & Persistence Baseline Engine]
        A3 --> A4[Walk-Forward Chronological Evaluator]
        A4 --> A5[Three-Tier Anomaly & Advisory Generator]
    end

    subgraph Phase 2: SUPPORTING
        B1[FastAPI Telemetry Ingress & Query Endpoints] --> B2[Local Redis / Stream Queue Buffer]
        B2 --> B3[Conditional Linear / GBDT Model Benchmark]
    end

    subgraph Phase 3: DEFERRED
        C1[Distributed Kafka / RabbitMQ Clusters]
        C2[Deep Learning Sequence Models LSTM/Transformers]
        C3[Autonomous Irrigation Actuation Hooks]
    end

    Phase 1 --> Phase 2
    Phase 2 -.-> Phase 3
```

### 2.1 Category Breakdown
- **MUST BUILD NOW (Phase 1):** The core Python package, deterministic station parser, schema validators, synthetic fault injector, state estimator, walk-forward persistence baseline, probabilistic quantile calculator, and test harness.
- **SUPPORTING (Phase 2):** Local SQLite / DuckDB persistence, lightweight FastAPI event receiver, and Docker Compose definition.
- **DEFERRED (Phase 3):** Kubernetes orchestration, distributed message brokers (Kafka/RabbitMQ), cloud data lakes, deep-learning frameworks (PyTorch/TensorFlow), and external proprietary farm APIs.

---

## 3. Detailed Component Plan (16 Modules)

### 3.1 Repository & Package Structure
- Root package: `agri_telemetry/`
  - `agri_telemetry/domain/`: Domain entities, value objects, scientific constants.
  - `agri_telemetry/contracts/`: JSON schema loaders, Pydantic/dataclass event models.
  - `agri_telemetry/ingestion/`: USCRN / SCAN parsers, replay iterator, timestamp normalizers.
  - `agri_telemetry/qc/`: Range checkers, spike filters, stuck-sensor detectors, fault labellers.
  - `agri_telemetry/state/`: Volumetric water content to root-zone depletion & available water fraction.
  - `agri_telemetry/forecasting/`: Persistence baseline, walk-forward backtester, metrics (MAE, RMSE, Pinball loss).
  - `agri_telemetry/alerts/`: 3-tier anomaly router (QC, Physical Residual, Agronomic MAD Risk).
  - `agri_telemetry/simulation/`: Fault injector (spikes, dropouts, frozen sensors).
  - `tests/`: Unit tests, integration tests, contract compliance tests, leakage tests.

### 3.2 Environment & Runtime
- Python 3.10+ virtual environment.
- Core dependencies: `pydantic>=2.0`, `jsonschema>=4.0`, `pandas>=2.0`, `numpy>=1.24`, `scipy>=1.10`, `pytest>=7.4`.
- Strict lockfile reproducibility via `requirements.txt` / `pyproject.toml`.

### 3.3 Data Acquisition
- Download and cache verified public station records (e.g. USCRN Nebraska/Kansas agricultural research stations).
- Local cache path: `data/raw/` with immutable checksum verification (`SHA256`).

### 3.4 Ingestion & Timestamp Normalization
- Parse sub-hourly / hourly station records into canonical `TelemetryEvent` structures.
- Enforce UTC ISO 8601 formatting.
- Explicitly split `event_time` (station reading time) from `ingest_time` (clock time at ingest).

### 3.5 Event Validation & Ingress QC
- Validate every raw dictionary against `telemetry-event.schema.json`.
- Apply rule-based QC filters:
  - VWC valid range: $[0.0, 0.65]\text{ m}^3/\text{m}^3$.
  - Soil Temperature range: $[-20.0, 50.0]^\circ\text{C}$.
  - Step-change $\Delta$ threshold: flag jumps $> 0.15\text{ m}^3/\text{m}^3\text{/hr}$ without precipitation.
- Tag events with `qc_flag` (`VALID`, `SUSPECT_SPIKE`, `SUSPECT_STUCK`, `OUT_OF_RANGE`).

### 3.6 Persistence & Deduplication State
- In-memory / lightweight SQLite key-value store indexing `event_id` and compound natural keys (`source_id + event_time`).
- Idempotent ingestion: reject or ignore duplicate records without mutating state.

### 3.7 Feature Generation & Lag Construction
- Construct temporal feature vectors strictly from $t \le t_{\text{origin}}$.
- Generate rolling lag windows ($t-1\text{h}, t-24\text{h}, t-168\text{h}$).
- Enforce strict time-travel leakage prevention assertions.

### 3.8 Forecasting Baseline (Persistence Benchmark)
- Implement `PersistenceBaseline`:
  $$\hat{Y}_{t+h|t} = Y_t \quad \forall h \in [1, 168\text{ hours}]$$
- Implement `DiurnalPersistenceBaseline` for atmospheric demand.
- Baseline must be beaten on out-of-sample data before any ML candidate is approved.

### 3.9 Uncertainty & Quantile Estimation
- Compute empirical historical residual distributions across forecast horizons $h \in \{6, 12, 24, 48, 72, 168\}\text{ hours}$.
- Generate calibrated quantiles ($q_{10}, q_{25}, q_{50}, q_{75}, q_{90}$) and $80\%$ prediction intervals.

### 3.10 Deviation & Agronomic Risk Logic
- Compute site-specific Management Allowable Depletion ($D_{\text{MAD}}$) exceedance probability:
  $$P(\text{Depletion}_{t+h} > D_{\text{MAD}} \mid \mathcal{F}_t)$$
- Emit `AlertEvent` if $P > \tau_{\text{threshold}}$ (e.g. $\tau = 0.75$).
- Preserve non-actuating advisory status (`is_autonomous_actuation: false`).

### 3.11 Synthetic Telemetry & Fault Injection
- Module to inject controlled, labeled synthetic anomalies into replay stream:
  - `VALUE_SPIKE`: inject unphysical sensor jump.
  - `SENSOR_STUCK`: repeat static float for $N$ timesteps.
  - `CLOCK_DRIFT`: shift `event_time` backward/forward.
  - `PACKET_DROP`: omit observations over a multi-hour window.
- Verify that injected faults are caught by Tier 1 QC and NEVER trigger Tier 3 Agronomic alerts.

### 3.12 Evaluation Engine
- Walk-forward backtesting loop.
- Metrics calculated per horizon $h$:
  - Mean Absolute Error ($\text{MAE}$)
  - Root Mean Squared Error ($\text{RMSE}$)
  - Continuous Ranked Probability Score ($\text{CRPS}$) / Quantile Pinball Loss
  - Prediction Interval Coverage Probability ($\text{PICP}$) for $80\%$ nominal coverage.

### 3.13 Observability & Structured Logging
- Structured JSON logging to stdout / file:
  - Fields: `timestamp`, `level`, `component`, `event_id`, `station_id`, `message`.
- Event counters: `events_ingested_total`, `events_qc_failed_total`, `forecasts_generated_total`, `alerts_emitted_total`.

### 3.14 Testing Suite
- `test_schemas.py`: Schema validation against valid/invalid JSON payloads.
- `test_qc_rules.py`: Verification of spike, range, and stuck-sensor detection.
- `test_leakage.py`: Temporal assertion tests guaranteeing no future data leaks into features or forecasts.
- `test_idempotency.py`: Verification that duplicate events do not corrupt state.
- `test_persistence.py`: Correct mathematical output of persistence baseline.
- `test_anomaly_isolation.py`: Verification that Tier 1 sensor faults do not trigger Tier 3 agronomic alerts.

### 3.15 Reproducibility Harness
- Single CLI entrypoint: `python -m agri_telemetry.cli run-pipeline --config config/sample_run.json`.
- Deterministic seed configuration.
- Markdown summary output written to `11. Evidence & Validation/`.

### 3.16 Documentation & Evidence Updates
- Record experiment runs in `11. Evidence & Validation/Evidence & Validation - Agri Telemetry & Forecasting Platform.md`.
- Transition statuses honestly (`DECIDED` $\to$ `IMPLEMENTED` $\to$ `TESTED` $\to$ `VALIDATED`).

---

## 4. Implementation Dependency Graph & Build Order

```text
Step 1: Contracts & JSON Schemas (Done)
   │
   ▼
Step 2: Core Domain Entities & QC Engine
   │
   ▼
Step 3: Station Ingestion & Synthetic Fault Simulator
   │
   ▼
Step 4: Persistence Baseline & Walk-Forward Evaluator
   │
   ▼
Step 5: Three-Tier Alert & Risk Evaluator
   │
   ▼
Step 6: Comprehensive Test Harness & Evidence Capture
```
