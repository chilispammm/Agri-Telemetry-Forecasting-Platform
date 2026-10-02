# ADR-008: Phase 4 Operational Architecture, Containerisation, Observability, and Stream Processing

## Status
**ACCEPTED** (Formally Adopted — Phase 4)

## Date
2026-10-02

## Context
Phases 1 through 3 established the scientific foundation and decision-support intelligence of the Agri Telemetry & Forecasting Platform:
- Real historical USCRN in-situ telemetry ingestion (Lincoln 11 SW, NE 2023)
- Tier-1 quality control with physical range, delta spike, and stuck sensor quarantine
- Multi-layer root-zone state construction and soil hydraulic depletion tracking
- Horizon-partitioned forecasting (Environmental Vector M2 for 1–48h, Statistical Autoregression M1 for 72–168h, Persistence Baseline B0 benchmark)
- Dynamic regime-conditioned uncertainty estimation (U2)
- Operational anomaly disambiguation (Tier-1 QC vs Physical Deviation vs Agronomic Water Risk)
- Multi-horizon risk evaluation with alert persistence filtering to suppress transient alarm noise while preserving non-actuating advisory safety.

Phase 4 transitions this validated scientific core into a **reproducible, observable, operationally resilient, and containerised engineering system** suited for production deployment. In accordance with the governing project principle (*"Build the evidence before building the complexity; What concrete engineering problem does this solve?"*), every operational component was introduced to address a specific production reliability, observability, or lifecycle requirement.

---

## Decision Drivers
1. **Reproducibility & Lineage:** Scientific results must be bit-for-bit reproducible across environments, with complete provenance linking code version (Git SHA), dataset version, hyperparameters, random seeds, and generated artifacts.
2. **Observability Separation:** Operational telemetry (latency percentiles, ingestion throughput, queue depth, error rates) must be strictly distinguished from domain scientific telemetry (forecast MAE/RMSE, empirical coverage, soil depletion fraction).
3. **Stream Processing Decoupling:** Ingestion, validation, state building, forecasting, and advisory emission must support asynchronous event streaming without introducing heavyweight cloud lock-in.
4. **Resilience & Fault Tolerance:** Ingested poison payloads or external inference service failures must not crash the stream consumer or interrupt monitoring of agricultural fields.
5. **Configuration Decoupling:** Scientific hydraulic parameters must be cleanly separated from operational infrastructure settings and runtime environment variables.

---

## Decisions

### 1. Configuration Management (`agri_telemetry.config.settings`)
We adopted a typed dataclass hierarchy (`AppConfig`) with clear separation of domains:
- **Scientific Configuration:** `SoilConfig` ($\theta_{fc}, \theta_{wp}, \theta_{sat}$, layer depths/weights), `RiskConfig` ($d_{mad}, d_{wilt}, \tau_{risk}$), and `ForecastingConfig` (horizons, model routing, uncertainty method).
- **Operational Configuration:** `StreamingConfig` (broker type, stream topics, batch sizes), `ObservabilityConfig` (log levels, formats, ports), `StorageConfig` (DB paths, runs directories), `MLOpsConfig` (backends, URIs), and `ReliabilityConfig` (retries, DLQ, fallback flags).
- **Declarative YAML & Environment Variables:** Support for declarative profiles (`config/default.yaml`, `config/production.yaml`) with explicit environment variable overrides (`AGRI_*`).

### 2. Structured Observability & Dual-Domain Metrics (`agri_telemetry.observability`)
- **JSON Logging & Tracing:** Implemented `JSONFormatter` providing contextualized structured logging with `correlation_id`, `run_id`, `stage`, `service`, `environment`, and ISO-8601 UTC timestamps.
- **Stage Timing Context:** Created `trace_stage` context manager enabling sub-millisecond instrumentation across contract validation, state construction, forecasting, and advisory evaluation.
- **Metrics Separation:** Implemented `MetricsCollector` and `LatencyTracker` maintaining explicit isolation between:
  - *Operational / System Metrics:* Events ingested, validation passes, quarantine counts, pipeline latency percentiles (p50, p90, p95, p99), error rates.
  - *Scientific / Domain Metrics:* Forecast MAE, RMSE, 80% interval empirical coverage, skill score vs persistence, latest depletion fraction, advisory counts by category and severity.

### 3. MLOps Lifecycle Tracking & Lineage (`agri_telemetry.mlops.experiment_tracker`)
- **Run Manifest Serialization:** `ExperimentTracker` generates self-contained `manifest.json` artifacts per run containing full provenance: Git commit SHA, dataset name/version/checksum, station ID, feature lists, hyperparameters, split strategy, execution timestamps, random seeds, and artifact references.
- **Pluggable Backends:** Standardized on zero-dependency local filesystem persistence as the canonical source of truth, with an optional pluggable MLflow client adapter for enterprise telemetry dashboards.

### 4. Event-Driven Streaming Architecture (`agri_telemetry.streaming`)
- **Abstract Broker Interface:** Defined `EventStreamBroker` protocol with standard `publish`, `consume`, `acknowledge`, `replay`, and `reset` contracts.
- **In-Memory & Redis Implementations:**
  - `InMemoryStreamBroker`: Zero-dependency, thread-safe, deterministic stream broker for unit testing, offline batch backtesting, and reproducibility verification.
  - `RedisStreamBroker`: Production-ready distributed stream broker utilizing Redis Streams (`XADD`, `XREADGROUP`, `XACK`) with consumer group scaling.
- **Stream Worker (`TelemetryStreamWorker`):** Decoupled worker consuming from `stream:telemetry`, executing Tier-1 QC and state construction, invoking forecast engines, evaluating advisories, and publishing to `stream:forecasts` and `stream:alerts`.

### 5. Reliability, Fault Tolerance & Graceful Degradation (`agri_telemetry.reliability.recovery`)
- **Dead Letter Queue (`DeadLetterQueue`):** Quarantines unparseable or schema-violating payloads with complete diagnostic error traces into `runs/dead_letter_queue.jsonl`.
- **Idempotency Filter (`EventDeduplicator`):** Hash-based sliding window deduplication preventing duplicate event ingestion.
- **Out-of-Order Sequencer (`OutOfOrderSequencer`):** Time-windowed buffering that restores chronological event ordering for delayed field sensor packets.
- **Resilient Forecast Router (`ResilientForecastRouter`):** Circuit-breaker wrapper that catches downstream forecast model exceptions and gracefully falls back to the deterministic Persistence Baseline (B0), guaranteeing uninterrupted operational advisory continuity.

### 6. Containerisation & CI/CD (`Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`)
- **Container Environment:** Minimal multi-stage Python 3.11-slim container with non-root security execution, parameterized configuration mounting, and optional Redis service orchestration.
- **Automated CI/CD:** GitHub Actions workflow executing code formatting checks, static analysis, the complete authoritative test suite, and the bit-for-bit reproducibility verification script on every pull request.

---

## Consequences

### Positive
- **Deterministic Reproducibility:** Verified zero discrepancy across independent runs on real historical data (`max_mae_discrepancy: 0.0`).
- **Production Readiness:** Full observability into processing latencies, error states, and model performance.
- **Fail-Safe Operation:** Telemetry streams cannot be stalled by poison messages; forecasting failures degrade gracefully to persistence.
- **Zero Cloud Lock-in:** The system runs identically in local Python environments, Docker containers, or distributed streaming clusters.

### Negative / Trade-offs
- Additional configuration layer requires careful parameter validation.
- Redis stream broker introduces an optional external operational dependency when deployed in distributed mode.

---

## Verification Evidence
- **Authoritative Test Suite:** All unit, integration, and operational tests executed and verified passing.
- **Reproducibility Verification Experiment:** `agri_telemetry/experiments/reproducibility_check.py` executed successfully with `is_reproducible: True` across 8,760 USCRN records.
