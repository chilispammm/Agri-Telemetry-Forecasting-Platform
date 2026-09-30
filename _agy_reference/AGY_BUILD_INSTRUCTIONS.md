# AGY BUILD INSTRUCTIONS — AGRI TELEMETRY & FORECASTING PLATFORM

## Mission

Complete the remaining specification documents and then build the minimum reproducible implementation for the Agri Telemetry & Forecasting Platform.

Primary goal: BUILD. Do not spend the session polishing already-frozen documents or inventing architecture.

## Source of Truth Hierarchy

1. `00_project/PROJECT_CHARTER.md`
2. `01_research/RESEARCH_FEASIBILITY.md`
3. `02_product/PRD.md`
4. `03_scientific/DATA_SCIENTIFIC_SPEC.md`
5. `04_forecasting/DATA_FORECAST_DESIGN.md`
6. `AGENTS.md`
7. `_reference/CA-ENG_DESIGN_SYSTEM.md`
8. Existing HTML files are visual references only; their content does not override canonical Markdown.

When sources conflict, stop and flag the contradiction in `09_evidence/DECISION_LOG.md`. Never silently choose.

## Frozen Documents

Treat the following as frozen unless a real contradiction requires correction:

- Project Charter
- Research Feasibility
- PRD
- Data & Scientific Specification
- Data & Forecast Design
- AGENTS.md

Do not rewrite their substantive content just to improve prose.

## Remaining Documents

Build in this order:

### 05 — Technical Specification

Create:
- `05_architecture/TECHNICAL_SPEC.md`
- `05_architecture/TECHNICAL_SPEC.html`

Define the simplest architecture satisfying the current product/scientific/forecast requirements. Keep MQTT vs HTTP, Redis Streams vs Kafka/RabbitMQ, MLflow scope, storage, API, and serving decisions evidence-driven. Include data flow, component boundaries, failure modes, observability, reproducibility, security basics, and local Docker Compose topology where justified.

### 06 — ADRs

Create:
- `06_decisions/ADR_INDEX.md`
- individual ADRs in `06_decisions/adr/`

Start with candidate ADRs for:
- primary data source
- transport
- streaming infrastructure
- forecast model
- MLOps scope

Do not mark an ADR DECIDED merely because a technology is convenient. Use status vocabulary from the project.

### 07 — Event / Telemetry Contract

Create:
- `07_contracts/EVENT_TELEMETRY_CONTRACT.md`
- `07_contracts/schemas/telemetry-event.schema.json`
- `07_contracts/schemas/alert-event.schema.json`

The contract must preserve event_id, source/device/station, sensor, site/field identifiers where applicable, event_time, ingest_time, sequence information where applicable, measurement, unit, quality, provenance, schema version, and idempotency semantics.

### 08 — Implementation Plan

Create:
- `08_implementation/IMPLEMENTATION_PLAN.md`

Keep it executable and short. Organise by vertical slices, dependencies, tests, evidence capture, and definition of done. Do not create a giant project-management document.

### 09 — Evidence / Validation Framework

Create:
- `09_evidence/EXPERIMENT_LOG.md`
- `09_evidence/VALIDATION_MATRIX.md`
- `09_evidence/DECISION_LOG.md`

This is a living evidence system. It must distinguish implementation evidence from scientific validation.

## HTML Rule

Only Technical Spec needs HTML now. Do not create HTML for ADRs, Implementation Plan, or Evidence unless explicitly requested.

When HTML is required:
- inspect `02_product/PRD.html` first;
- use `_reference/CA-ENG_DESIGN_SYSTEM.md`;
- preserve the established boutique editorial look;
- do not invent new component classes;
- header pattern: `Agri Telemetry & Forecasting Platform` / `Last Edited: DD MON YYYY / Status: ...`;
- metadata/navigation may be uppercase; document and section titles should remain clean and readable.

## Scientific Guardrails

Never:
- fabricate metrics, tests, experiments, data, validation, or benchmarks;
- claim USCRN is validated before station audit;
- claim persistence was beaten before running the experiment;
- hard-code a universal MAD threshold;
- use realised future weather as operational forecasting input;
- call reanalysis or satellite data field ground truth without qualification;
- infer crop stress from a sensor anomaly;
- treat N-of-M breaches as alpha^N independent false-alarm probabilities;
- add deep learning merely for portfolio signalling.

Persistence is mandatory.
Chronological / walk-forward evaluation is mandatory.
Final test must remain untouched until selection is complete.

## Build Philosophy

Prefer a small, end-to-end, testable vertical slice over partially implementing many technologies.

The implementation should demonstrate:

1. ingest or replay real historical telemetry;
2. preserve provenance and temporal semantics;
3. simulate a realistic telemetry/event stream;
4. process events idempotently where duplicates can occur;
5. produce at least a baseline forecast;
6. record forecast/evaluation metadata;
7. support explicit uncertainty where actually implemented;
8. generate a risk/alert object only where a defensible threshold definition exists;
9. run reproducibly with documented commands.

Do not build a dashboard before the underlying pipeline is proven.

## Evidence Discipline

Every implemented capability should have:
- test coverage;
- reproducible command;
- recorded result;
- documentation status matching evidence.

Passing tests are not scientific validation.
A successful demo is not generalisation evidence.
Implementation is not validation.

## Working Behaviour

- Inspect before editing.
- Reuse existing files and conventions.
- Make the smallest defensible change.
- Keep Markdown canonical.
- Keep HTML substantively aligned with Markdown.
- Run focused tests before broad tests.
- Record failures instead of hiding them.
- If an unresolved decision blocks implementation, choose the simplest reversible option only when it does not contradict a requirement, and record it as OPEN/ASSUMPTION rather than pretending it is validated.

## Definition of Done

A slice is complete when:

1. it runs reproducibly;
2. required edge cases are handled;
3. focused tests pass;
4. evidence is recorded;
5. relevant documentation is updated;
6. an ADR is created/updated for a material architectural decision;
7. status reflects actual evidence.
