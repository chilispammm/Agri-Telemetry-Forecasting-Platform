# Agri Telemetry & Forecasting Platform — Architecture Decision Records (ADRs)

**Status:** ACTIVE  
**Last Updated:** September 30, 2026  
**Document:** `06_decisions/ADR_INDEX.md` / `8. ADRs/ADR_INDEX.md`

---

## 1. ADR Governance

Every architectural decision that materially impacts system behavior, data integrity, forecasting methodology, or infrastructure complexity requires an Architecture Decision Record.

### Status Terminology:
- **PROPOSED:** Under review and discussion.
- **DECIDED:** Formally approved based on demonstrable project requirements.
- **IMPLEMENTED:** Built and verified in the codebase.
- **SUPERSEDED:** Replaced by a subsequent ADR.
- **REJECTED:** Evaluated and discarded.

---

## 2. ADR Index

| ADR ID | Title | Status | Date | Decision Summary |
| :--- | :--- | :--- | :--- | :--- |
| [**ADR-001**]() | Primary Data Source & In-Situ Research Network Selection | **DECIDED** | 2026-09-30 | Adopt USCRN/SCAN standardized public in-situ soil moisture stations as canonical primary reference source for baseline development. |
| [**ADR-002**]() | Event Ingestion Transport Protocol | **DECIDED** | 2026-09-30 | Standardize on HTTP/JSON REST and local file replay for vertical slice; defer MQTT/gRPC until physical gateway requirements emerge. |
| [**ADR-003**]() | Stream Processing & Buffer Architecture | **DECIDED** | 2026-09-30 | Use lightweight in-memory / local worker queue with idempotent deduplication; defer heavy Kafka/RabbitMQ clusters. |
| [**ADR-004**]() | Mandatory Forecasting Baseline & Benchmark Hierarchy | **DECIDED** | 2026-09-30 | Enforce persistence and diurnal persistence baselines as non-negotiable benchmark before deploying conditional regression or GBDTs. |
| [**ADR-005**]() | MLOps & Experiment Tracking Scope | **DECIDED** | 2026-09-30 | Adopt lightweight structured JSON/Markdown experiment ledger with deterministic seed locking; defer heavy hosted MLflow servers. |
| [**ADR-006**]() | Horizon-Partitioned Forecasting Architecture & NWP Ingress Boundary | **DECIDED** | 2026-10-02 | Adopt hybrid forecasting model (M2 for 1-48h, M1 for 72-168h) to guarantee positive skill across all horizons; formalize NWP forecast ingress contract. |
| [**ADR-007**]() | Operational Anomaly Taxonomy, Multi-Horizon Water Risk Evaluation, and Alert Persistence Filter Architecture | **DECIDED** | 2026-10-02 | Establish 3-tier anomaly isolation boundary, uncertainty-aware risk certainty levels, and stateful persistence filtering to suppress false alarms. |
| [**ADR-008**]() | Phase 4 Operational Architecture, Containerisation, Observability, and Stream Processing | **DECIDED** | 2026-10-02 | Establish unified configuration hierarchy, dual-domain metrics, structured tracing, MLOps lineage tracking, streaming broker workers, and DLQ resilience. |

