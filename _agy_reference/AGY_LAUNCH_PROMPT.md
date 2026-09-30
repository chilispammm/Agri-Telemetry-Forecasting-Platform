# AGY LAUNCH PROMPT

You are the implementation/build agent for the **Agri Telemetry & Forecasting Platform**.

The project is intentionally evidence-first, but the specification phase is now sufficiently mature to move into BUILD. The objective for this session is to complete the remaining specification files and build the smallest credible end-to-end vertical slice. Do not spend the session polishing existing documents.

## Read first

1. `AGENTS.md`
2. `_reference/CA-ENG_DESIGN_SYSTEM.md`
3. `00_project/PROJECT_CHARTER.md`
4. `01_research/RESEARCH_FEASIBILITY.md`
5. `02_product/PRD.md`
6. `02_product/PRD.html`
7. `03_scientific/DATA_SCIENTIFIC_SPEC.md`
8. `04_forecasting/DATA_FORECAST_DESIGN.md`
9. `_reference/PROJECT_AND_RESEARCH_SOURCE.md`

Treat the Markdown specifications as canonical. Use `PRD.html` and the CA-ENG reference as the visual language for any HTML you create.

## Do not ask for confirmation

Make reasonable, reversible choices where needed. Record unresolved choices as `OPEN` or `ASSUMPTION`. Do not silently convert uncertainty into a decision.

## Remaining specification work

Create:

- `05_architecture/TECHNICAL_SPEC.md`
- `05_architecture/TECHNICAL_SPEC.html`
- `06_decisions/ADR_INDEX.md`
- `06_decisions/adr/ADR-001-data-source.md`
- `06_decisions/adr/ADR-002-transport.md`
- `06_decisions/adr/ADR-003-streaming.md`
- `06_decisions/adr/ADR-004-forecast-model.md`
- `06_decisions/adr/ADR-005-mlops.md`
- `07_contracts/EVENT_TELEMETRY_CONTRACT.md`
- `07_contracts/schemas/telemetry-event.schema.json`
- `07_contracts/schemas/alert-event.schema.json`
- `08_implementation/IMPLEMENTATION_PLAN.md`
- `09_evidence/EXPERIMENT_LOG.md`
- `09_evidence/VALIDATION_MATRIX.md`
- `09_evidence/DECISION_LOG.md`

Only the Technical Spec gets HTML in this phase.

## Technical design rule

Choose the smallest architecture that satisfies the requirements actually present in the source documents.

Do not add MQTT, Redis Streams, Kafka, RabbitMQ, MLflow, orchestration, databases, cloud infrastructure, dashboards, deep learning, or other components merely because they look good on a portfolio.

Where evidence is insufficient, keep the decision open or choose the simplest reversible path and document it.

## Build goal

After the documents are created, build a minimal end-to-end vertical slice capable of:

1. obtaining/replaying an approved historical telemetry source;
2. preserving provenance and temporal semantics;
3. generating simulated telemetry from real history rather than arbitrary random data;
4. injecting labelled synthetic event faults;
5. validating and processing telemetry events;
6. handling duplicates/idempotency where the chosen event design requires it;
7. producing a persistence baseline forecast;
8. evaluating the baseline chronologically/walk-forward;
9. producing a basic forecast/evaluation artefact;
10. recording experiment metadata;
11. exposing a risk/alert object only when a defensible threshold is actually available.

A complete polished dashboard is NOT a requirement for this build session.

## Scientific guardrails

Never fabricate:

- dataset values;
- metrics;
- tests;
- station validation;
- forecast performance;
- uncertainty calibration;
- threshold performance;
- operational outcomes.

USCRN remains a candidate until an actual station audit is performed.

Do not hard-code a universal MAD number.

Do not use realised future weather as an operational forecasting feature.

Do not call reanalysis/satellite data field ground truth.

Do not equate anomaly with crop stress.

Do not claim N consecutive interval breaches have probability alpha^N unless independence has actually been established.

## HTML rules

When creating `TECHNICAL_SPEC.html`:

- inspect `02_product/PRD.html` before writing it;
- copy the established CA-ENG editorial/brutalist-clean visual grammar;
- use the header pattern:
  `Agri Telemetry & Forecasting Platform` / `Last Edited: DD MON YYYY / Status: ...`;
- document title and section headings should be readable/title case, not forced uppercase;
- navigation and metadata may use uppercase;
- use only approved CA-ENG components;
- no inline styles;
- no invented utility classes;
- no gradients, decorative icons, rounded app-style UI, or unnecessary animation.

## Testing

Start with focused tests for the vertical slice. Do not spend excessive time running every possible test suite if the implementation is still changing.

At minimum, test the behaviours actually implemented, such as:

- schema validation;
- provenance preservation;
- event-time vs ingestion-time distinction;
- duplicate handling/idempotency;
- delayed/out-of-order handling if supported;
- synthetic fault labelling;
- persistence forecast correctness;
- chronological forecast evaluation;
- reproducibility of the experiment command.

Record actual results in `09_evidence/`.

## Definition of done for tonight

The session is successful when:

- remaining core documents exist;
- Technical Spec HTML matches the established style;
- ADR statuses match actual evidence;
- telemetry contract and JSON schemas exist;
- implementation plan is executable;
- evidence framework exists;
- a small end-to-end slice runs locally;
- focused tests pass and results are recorded;
- README/project entry point explains how to run it;
- no invented validation claims have been introduced.

Finish by reporting:

1. files created;
2. architectural decisions actually made;
3. unresolved/open decisions;
4. commands to run the system;
5. tests run and real results;
6. known limitations;
7. the next highest-value empirical experiment.
