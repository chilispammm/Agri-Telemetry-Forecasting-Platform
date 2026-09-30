# Agri Telemetry & Forecasting Platform — Agent Instructions

**Status:** ACTIVE
**Scope:** Repository-wide Engineering Constitution

This file governs the behaviour of all coding agents, AI assistants, and developers operating within this repository. These rules are non-negotiable and supersede generic AI programming advice.

---

## 1. Non-Negotiable Principles

1. **Never fabricate data, metrics, tests, experiments, validation results, or scientific findings.**

2. **Never mark something VALIDATED without project-specific evidence.**

3. **Never present simulated telemetry as observed telemetry.**

4. **Never represent reanalysis or modelled products (e.g. ERA5-Land/Open-Meteo) as ground-truth field observations.**

5. **Preserve dataset provenance:** maintain source, timestamps, units, quality flags, identifiers, retrieval information, and other relevant provenance explicitly.

6. **Never use future information in historical forecasting experiments.**

7. **Persistence is the mandatory baseline for forecasting experiments unless the experiment is explicitly unrelated to forecasting.**

8. **Use chronological or walk-forward evaluation for time-series forecasting.**

9. **Never use random train/test splitting for temporal forecasting unless explicitly justified and leakage is definitively mitigated.**

10. **Separate point forecasting from probabilistic forecasting.**

11. **Use prediction intervals, predictive distributions, or another explicitly justified uncertainty method when making probabilistic or uncertainty claims.**

12. **Separate data-quality anomalies** (e.g. dropped packets, malformed values, sensor drift) **from physical/environmental deviations** (e.g. unexpected wetting or drying) **and agronomic/operational risk** (e.g. threshold-crossing risk).

13. **Do not turn a model deviation into a claim of crop stress without evidence.**

14. **Do not hard-code universal agronomic thresholds without documented scientific and project-specific justification.**

15. **Do not add infrastructure merely because it demonstrates a technology.**

16. **MQTT, Redis Streams, Kafka, RabbitMQ, MLflow, deep-learning frameworks, orchestration systems, and other significant technologies require explicit justification against demonstrated requirements.**

17. **Architecture changes that materially alter system behaviour require an Architecture Decision Record (ADR).**

18. **Keep the simplest architecture that satisfies demonstrated requirements.**

19. **Every experiment must identify its context:** dataset/source and version, time period, split strategy, horizon, features, target definition, model, metrics, code/version, and relevant configuration. Record a random seed where randomness is used.

20. **Final test data must remain untouched during model, feature, hyperparameter, and threshold selection.**

21. **Synthetic faults must be labelled and clearly distinguishable from real observations.**

22. **Event processing must account for duplicates, delayed messages, out-of-order events, and reconnects where applicable.**

23. **Downstream processing must be designed for idempotency where duplicate delivery is possible.**

24. **Do not silently change schemas, event contracts, units, or interfaces.**

25. **Do not silently substitute one dataset, source, variable, or processing method for another when the intended source is unavailable.** Any substitution must be explicit, documented, and traceable.

26. **Do not delete contradictory or anomalous observations merely because they make the model cleaner.** Handle them according to the documented scientific and data-quality policy.

27. **Distinguish event time from ingestion/processing time.** Do not use ingestion order as a substitute for event chronology unless explicitly justified.

28. **Do not silently convert between observed, derived, simulated, and modelled variables.** Their provenance and representation must remain explicit.

29. **Do not optimise for impressive architecture.** Optimise for evidence, reproducibility, and demonstrated decision value.

30. **Documentation status must reflect evidence, not implementation progress.** Code being implemented or tested does not by itself make a scientific hypothesis or architectural decision VALIDATED.

---

## 2. Status Terminology

Use these status labels consistently and honestly across all documentation and execution logs:

* **OPEN:** Not investigated or no decision made yet.
* **ASSUMPTION:** Currently believed, but unverified by project evidence.
* **RESEARCHING:** Investigation, literature review, or experimentation is actively underway.
* **DECIDED:** A decision has been made based on evidence and reasoning, typically resulting in an ADR, but it is not yet built or empirically validated as an implementation.
* **IMPLEMENTED:** Code has been written.
* **TESTED:** Code has passed defined programmatic tests.
* **VALIDATED:** Supported by empirical project evidence, such as an out-of-sample experiment confirming a hypothesis or an end-to-end test demonstrating a required system behaviour.
* **REJECTED:** Investigated and intentionally discarded.

A component may therefore be **IMPLEMENTED** or **TESTED** without being scientifically **VALIDATED**.

---

## 3. Before You Build — Agent Pre-Flight Checklist

**STOP.** Before implementing new features, modifying core logic, changing data processing, or adding dependencies, inspect the relevant foundational documents:

* `00_project/PROJECT_CHARTER.md`
* `01_research/RESEARCH_FEASIBILITY.md` *(when available)*
* `02_product/PRD.md` *(when available)*
* `03_scientific/DATA_SCIENTIFIC_SPEC.md` *(when available)*
* `04_forecasting/DATA_FORECAST_DESIGN.md` *(when available)*
* `05_architecture/TECHNICAL_SPEC.md` *(when available)*
* `06_decisions/ADR_INDEX.md` *(and relevant ADR files, when available)*
* `07_contracts/EVENT_TELEMETRY_CONTRACT.md` *(when available)*

Ensure the proposed change aligns with the current status, scope, constraints, and decisions established in these documents.

If relevant documentation is missing or contradictory, **do not invent the missing decision**. Report the conflict or gap before proceeding.

---

## 4. Before You Change Architecture

If a task requires adding a database, modifying a message broker, changing the transport protocol, introducing a substantial infrastructure component, or adding a heavy dependency such as a deep-learning framework or orchestration layer, **stop before implementing the structural change** and present:

1. **Requirement being solved**
2. **Current behaviour**
3. **Proposed change**
4. **Evidence supporting the change**
5. **Trade-offs**
6. **Affected contracts**
7. **Tests required**
8. **ADR requirement:** whether an ADR must be drafted or updated

The structural change must not be implemented until the required decision has been made.

---

## 5. Evidence Requirements

Do not prescribe or implement technologies that have not yet been decided.

Do not invent project-specific implementation details that are not supported by the current specifications or evidence.

### Experiments

Every substantive experiment must record, as applicable:

* Dataset/source and version
* Retrieval date or data snapshot
* Time period
* Target definition
* Feature definitions
* Preprocessing
* Missing-data policy
* Quality-control policy
* Train/validation/test methodology
* Forecast horizon
* Model/baseline
* Hyperparameters
* Random seed where applicable
* Metrics
* Code/configuration version
* Relevant assumptions
* Results
* Limitations

### Forecasting

Forecasting evaluation must:

* include Persistence as the baseline;
* use chronological/walk-forward evaluation;
* prevent future information leakage;
* report results by explicitly defined horizon;
* distinguish point-forecast metrics from probabilistic metrics;
* preserve an untouched final test period.

The specific horizons to evaluate are determined by the current Forecast Design and experimental requirements. Candidate horizons must not be treated as permanently fixed merely because they appear in earlier research.

### Threshold / Risk Alerts

Any threshold-risk experiment must explicitly document:

* the state representation being thresholded;
* the agronomic threshold definition;
* the source or justification for the threshold;
* the uncertainty method;
* the alert/persistence rule;
* the evaluation period;
* the false-alert and lead-time criteria.

A numeric MAD value must not be invented merely to make an implementation executable.

### Data and Provenance

Every transformation must preserve sufficient information to determine:

**where the data came from → what was changed → why it was changed → what representation was produced.**

Observed, derived, simulated, and modelled data must remain distinguishable throughout the pipeline.

---

## 6. Reproducibility

A result described as reproducible must include sufficient information for another run to recreate it, including where applicable:

* dependency/environment versions;
* configuration;
* dataset/source identifier;
* retrieval date;
* data snapshot or checksum;
* preprocessing version;
* model/version;
* random seed;
* code revision;
* execution parameters.

Do not claim reproducibility when the required inputs or configuration are unavailable.

---

## 7. Definition of Done

A component, experiment, or architectural change is only considered **Done** when:

1. It executes reproducibly within its defined environment.
2. It handles its explicit constraints, such as leakage prevention, idempotency, provenance, or schema validation.
3. Relevant tests have been executed and their results recorded.
4. Results, schemas, assumptions, or implementation details have been documented in the relevant `.md` specification or evidence file.
5. Any confirmed or rejected architectural decision has the relevant ADR created or updated.
6. The documented status accurately reflects the evidence available.

**Implementation is not validation.**

**Passing tests are not scientific validation.**

**A successful demo is not evidence of generalisation.**

---

## 8. Agent Behaviour

When uncertainty exists:

* **Do not guess.**
* **Do not silently choose the most sophisticated option.**
* **Do not convert an assumption into a fact.**
* **Do not hide failed experiments.**
* **Do not overwrite contradictory evidence.**
* **Do not optimise metrics at the expense of leakage or scientific validity.**
* **Do not expand scope simply because a technology is available.**

Instead:

**Identify the uncertainty → state the assumption → gather evidence → test it → record the result → update the decision.**

This repository follows:

> **PLAN → RESEARCH → SPECIFY → BUILD → TEST → MEASURE → REVIEW → UPDATE**

and the governing principle:

> **Build the evidence before building the complexity.**
