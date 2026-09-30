# Agri Telemetry & Forecasting Platform — Product Requirements Document

**Status:** RESEARCHING
**Last Updated:** September 30, 2026
**Document:** `02_product/PRD.md`

---

## 01. Document Purpose

This Product Requirements Document (PRD) defines what the Agri Telemetry & Forecasting Platform must do, who it is intended to support, what decisions it is intended to inform, and how product success will be evaluated.

It translates the project intent and research findings into observable product requirements.

This document does **not** prescribe the final dataset, forecasting model, transport protocol, message broker, infrastructure, or implementation architecture. Those decisions belong to the Data/Scientific Specification, Forecast Design, Technical Specification, and ADRs.

---

## 02. Product Definition

**Product Name:** Agri Telemetry & Forecasting Platform

**Product Type:** Operational agricultural time-series intelligence system.

**Core Product Function:**

> Transform incoming agricultural telemetry into a trustworthy representation of soil-water state, forecast its near-term trajectory with quantified uncertainty, and identify potential management-threshold risks early enough to support an operational decision.

The product is therefore not simply a:

* sensor dashboard;
* soil-moisture predictor;
* anomaly detector;
* weather-monitoring system; or
* generic IoT pipeline.

Its value depends on connecting **telemetry → temporal state → forecast → uncertainty → operational risk**.

---

## 03. Product Problem

Agricultural telemetry can provide frequent observations of environmental and soil conditions, but raw sensor changes are not inherently actionable.

A decrease in measured soil moisture may reflect normal drying, weather conditions, irrigation history, sensor behaviour, or a genuine developing water-status risk. Likewise, a statistical anomaly does not automatically constitute crop stress.

The product must therefore help distinguish between:

1. **Data-quality problems** — the telemetry itself may be unreliable.
2. **Physical/environmental deviations** — observed conditions differ from the expected temporal behaviour.
3. **Forecasted state risk** — the projected trajectory approaches a relevant management threshold.
4. **Operational risk** — the projected condition may require attention within the available decision window.

The product must preserve these distinctions rather than collapsing them into a single generic "alert".

---

## 04. Target User

**Primary user:** `[ OPEN — to be resolved through product research ]`

Candidate users include:

* farm managers;
* irrigation managers;
* agronomists;
* agricultural operations teams.

The initial implementation may use a technical/research user as the effective operator because the system is a portfolio-scale prototype rather than a deployed commercial product.

The final user definition must be established before product-level workflow and interface requirements are frozen.

---

## 05. User / Operational Job

The product should support an operator who needs to answer questions such as:

> **What is the current soil-water state, how is it changing, where is it expected to go, and is there enough lead time to act if the trajectory approaches a relevant management threshold?**

Depending on the eventual operating context, this may include:

* determining whether observed drying is expected;
* identifying unusual wetting or drying;
* assessing whether a sensor or telemetry stream is behaving abnormally;
* estimating where the soil-water state is heading;
* quantifying uncertainty around that forecast;
* identifying potential threshold-crossing risk;
* understanding the available lead time;
* distinguishing an alert that requires investigation from one that may require an agronomic/operational response.

The system is a **decision-support tool**, not an autonomous irrigation controller.

---

## 06. Product Objective

The product must demonstrate that an agricultural telemetry system can:

1. receive and preserve time-stamped observations;
2. maintain trustworthy temporal state;
3. detect relevant data-quality and physical deviations;
4. produce reproducible near-term forecasts;
5. quantify forecast uncertainty;
6. identify potential management-threshold risk;
7. communicate sufficient evidence and context for an operator to assess the result.

---

## 07. Core Product Workflow

The product's conceptual workflow is:

```text
Telemetry
    ↓
Data / Event Integrity
    ↓
State Reconstruction
    ↓
Forecast
    ↓
Predictive Uncertainty
    ↓
Deviation / Threshold Assessment
    ↓
Operational Risk
```

This is a **product reasoning flow**, not a commitment to a particular technical architecture.

---

# 08. Functional Requirements

## FR-01 — Telemetry Ingestion

The system shall accept time-stamped agricultural telemetry from the selected data source or simulated telemetry source.

The system shall preserve, where applicable:

* source/station/device identifier;
* sensor identifier;
* field/site identifier;
* event timestamp;
* ingestion timestamp;
* measurement;
* unit;
* quality status;
* provenance;
* schema/version information.

The final transport mechanism remains an open technical decision.

---

## FR-02 — Provenance Preservation

The system shall distinguish between:

* observed measurements;
* derived variables;
* simulated telemetry;
* synthetic faults;
* modelled/reanalysis data;
* forecast values.

A downstream user shall be able to determine the provenance and transformation history of a value used by the system.

---

## FR-03 — Data-Quality Assessment

The system shall identify or expose relevant telemetry-quality problems, including where applicable:

* missing observations;
* malformed values;
* duplicate events;
* delayed events;
* out-of-order events;
* implausible values;
* communication gaps;
* sensor drift or abnormal behaviour.

Data-quality anomalies shall not automatically be classified as physical or agronomic events.

---

## FR-04 — Temporal State Reconstruction

The system shall construct the temporal representation required by the forecasting and risk-assessment process from incoming observations.

The representation must retain sufficient temporal and provenance information to distinguish:

* what was observed;
* when it occurred;
* when it was received;
* what was derived from it.

The final state representation remains subject to the Data/Scientific Specification.

---

## FR-05 — Near-Term Forecasting

The system shall generate forecasts of the selected soil-water state or trajectory over explicitly defined future horizons.

Forecasts shall:

* use only information available at the forecast origin;
* prevent temporal leakage;
* include Persistence as a mandatory baseline;
* be evaluated using chronological/walk-forward methodology;
* report performance by forecast horizon.

The final forecast horizons are not yet fixed.

---

## FR-06 — Probabilistic Forecasting

Where the product makes uncertainty claims, it shall provide an explicitly defined representation of predictive uncertainty.

This may take the form of:

* prediction intervals;
* predictive quantiles;
* predictive distributions;
* or another scientifically justified method.

The selected method shall be defined in the Forecast Design and evaluated empirically.

A prediction interval shall not be described as a confidence interval unless it is specifically a confidence interval.

---

## FR-07 — Deviation Detection

The system shall identify meaningful deviations between observed behaviour and the expected temporal baseline where the available evidence supports such detection.

Deviation detection shall distinguish, where possible:

* telemetry/data-quality deviation;
* physical/environmental deviation;
* model/forecast deviation.

A deviation shall not automatically be interpreted as crop stress.

---

## FR-08 — Threshold-Risk Assessment

The system shall support assessment of whether the forecast trajectory approaches or crosses a relevant management threshold.

The threshold:

* must be explicitly defined;
* must have documented scientific/project justification;
* must not be a universal hard-coded value;
* must account for the selected state representation.

The system shall distinguish **threshold risk** from confirmed crop stress.

---

## FR-09 — Alert Persistence / Confirmation

Where alerts are generated from sequential observations or forecasts, the system shall support an explicit persistence/confirmation rule where justified.

The rule shall be evaluated empirically rather than assuming that consecutive observations are statistically independent.

The final alert rule remains open.

---

## FR-10 — Alert Context

A risk alert shall provide sufficient context for an operator to understand why it was generated.

Where applicable, this should include:

* affected site/device/sensor;
* event or forecast time;
* observed state;
* expected state;
* forecast trajectory;
* uncertainty;
* relevant threshold;
* estimated lead time;
* alert classification;
* relevant data-quality status;
* provenance.

The final presentation mechanism is not prescribed by this PRD.

---

## FR-11 — Historical Evaluation

The system shall support reproducible evaluation against historical data.

Evaluation shall preserve:

* chronological ordering;
* defined training/validation/test periods;
* an untouched final test period;
* explicit forecast horizons;
* baseline comparisons;
* model/configuration versions;
* evaluation metrics;
* relevant assumptions and limitations.

---

## FR-12 — Synthetic Telemetry

The system may generate a controlled telemetry stream from historical observations for event-processing experiments.

Synthetic telemetry shall remain distinguishable from the underlying observed data.

Controlled faults may include:

* packet loss;
* duplicate events;
* delayed delivery;
* out-of-order delivery;
* reconnects;
* abnormal readings;
* other explicitly defined fault conditions.

Synthetic faults must be labelled and traceable.

---

## FR-13 — Event Integrity

Where the system processes event streams, it shall preserve enough information to distinguish event chronology from ingestion or processing order.

The system shall be capable of handling relevant event-processing conditions such as:

* duplicate delivery;
* delayed delivery;
* out-of-order events;
* reconnects;
* consumer interruption.

Downstream processing shall be idempotent where duplicate delivery is possible.

---

## FR-14 — Reproducible Experiments

The system shall support reproducible experiments with sufficient metadata to reconstruct:

* dataset/source and version;
* retrieval date or snapshot;
* time period;
* target definition;
* features;
* preprocessing;
* missing-data policy;
* quality-control policy;
* train/validation/test methodology;
* forecast horizon;
* model/baseline;
* hyperparameters;
* random seed where applicable;
* metrics;
* code/configuration version;
* assumptions;
* results;
* limitations.

---

# 09. Product Output Requirements

The product should ultimately produce three related classes of output.

### 09.1 State Output

A trustworthy representation of the current/recent soil-water state.

### 09.2 Forecast Output

A near-term trajectory with an explicit representation of uncertainty.

### 09.3 Risk Output

A classification or alert indicating potential deviation or threshold-crossing risk, accompanied by sufficient context to evaluate the signal.

These outputs must remain distinguishable.

A forecast is not an observation.

An anomaly is not automatically a risk.

A risk signal is not confirmation of crop stress.

---

# 10. Non-Functional Requirements

## NFR-01 — Reproducibility

The complete experimental pipeline must be reproducible within the defined local environment.

---

## NFR-02 — Traceability

A reported result must be traceable to its:

```text
Source → Transformation → Experiment → Model → Evaluation → Result
```

---

## NFR-03 — Temporal Integrity

No future information may enter a historical forecast experiment through:

* features;
* preprocessing;
* aggregation;
* scaling;
* imputation;
* model selection;
* threshold selection;
* or evaluation.

---

## NFR-04 — Scientific Integrity

The system must not represent:

* simulated data as observations;
* reanalysis as field telemetry;
* statistical deviation as crop stress;
* model performance as generalised performance without appropriate validation.

---

## NFR-05 — Operational Simplicity

The product should minimise infrastructure and operational complexity unless additional complexity is justified by demonstrated requirements.

---

## NFR-06 — Testability

Core product behaviour shall be testable independently, including where applicable:

* event validation;
* provenance;
* temporal ordering;
* duplicate handling;
* idempotency;
* forecasting;
* uncertainty;
* threshold assessment;
* alert persistence.

---

## NFR-07 — Observability

The system should expose sufficient information to determine:

* whether telemetry is arriving;
* whether data quality is degrading;
* whether processing is delayed;
* whether forecasts are being generated;
* whether model outputs remain within expected operating conditions.

The exact observability implementation remains a technical decision.

---

# 11. Product Success Criteria

The product is successful only if it demonstrates **decision-relevant value**, not merely technical operation.

Success requires evidence that the system can:

### A. Process

Reliably ingest and process the selected telemetry representation while preserving provenance and temporal integrity.

### B. Forecast

Produce reproducible forecasts that are evaluated against Persistence and other justified baselines.

### C. Quantify Uncertainty

Produce uncertainty estimates whose empirical performance is measured rather than assumed.

### D. Detect

Identify predefined deviations or threshold-crossing events out-of-sample where the data supports such evaluation.

### E. Provide Lead Time

Quantify how early relevant events can be detected before the defined operational threshold or event.

### F. Control False Alerts

Measure the false-alert burden rather than optimising solely for sensitivity.

### G. Reproduce

Allow the complete experiment to be rerun from a documented environment, configuration, dataset/source, and code revision.

### H. Explain

Provide sufficient context to distinguish a data-quality issue, physical deviation, forecast uncertainty, and agronomic/operational risk.

---

# 12. Product-Level Acceptance Criteria

The initial product prototype should not be considered complete unless it can demonstrate, with project evidence:

* [ ] A defined and documented user/decision context.
* [ ] A documented telemetry source and provenance model.
* [ ] Validated handling of relevant telemetry-quality conditions.
* [ ] A reproducible temporal forecasting experiment.
* [ ] Persistence benchmark results.
* [ ] Chronological/walk-forward evaluation.
* [ ] An untouched final test period.
* [ ] Explicit uncertainty evaluation where probabilistic forecasts are used.
* [ ] A documented deviation/threshold-risk definition.
* [ ] Quantified alert performance, including lead time and false-alert burden where applicable.
* [ ] Reproducible event-processing behaviour under defined synthetic faults.
* [ ] Idempotent downstream processing where duplicate delivery is possible.
* [ ] Traceable experiment and model metadata.
* [ ] Documentation that accurately reflects the evidence obtained.

---

# 13. Explicit Non-Goals

The initial product will **not** attempt to:

* physically deploy agricultural hardware;
* control irrigation equipment automatically;
* provide universal irrigation recommendations;
* claim field-wide conditions from a single point sensor without supporting evidence;
* provide crop-stress diagnosis solely from telemetry anomalies;
* perform seasonal or multi-month drought forecasting;
* provide a full commercial farm-management platform;
* integrate proprietary farm-management APIs;
* build a production-scale cloud platform;
* introduce deep learning solely for portfolio signalling;
* introduce complex streaming infrastructure solely to demonstrate technology;
* provide a full-scale dashboard before the underlying data, forecasting, and API behaviour are proven.

---

# 14. Product Boundaries

The product begins at:

> **Reliable agricultural telemetry becoming available to the system.**

The product ends at:

> **A reproducible, uncertainty-aware assessment of temporal state and potential operational risk.**

The product does not claim responsibility for:

* physical sensor installation;
* irrigation execution;
* agronomic diagnosis;
* farm-wide representativeness beyond the validated observation context;
* the correctness of external weather forecasts;
* operational decisions made by a human user.

---

# 15. Open Product Questions

The following remain unresolved and must be answered before the relevant downstream specifications are frozen:

1. Who is the primary decision-maker?
2. What specific operational decision is being supported?
3. What is the final soil-water state representation?
4. What constitutes a meaningful deviation?
5. What constitutes an actionable threshold risk?
6. What forecast horizons have sufficient decision value?
7. What information is available to the operator at forecast time?
8. How should uncertainty be communicated?
9. What constitutes an acceptable false-alert burden?
10. What lead time is operationally useful?
11. How should irrigation information be represented when observed irrigation data is unavailable?
12. What level of spatial/site generalisation is required?
13. What is the minimum product interface required to demonstrate decision value?

These questions should be resolved through the appropriate downstream specification or empirical experiment rather than assumed in the PRD.

---

# 16. Traceability

| Requirement Area                     | Primary Authority                          |
| ------------------------------------ | ------------------------------------------ |
| Project purpose and boundaries       | `00_project/PROJECT_CHARTER.md`            |
| Feasibility and research evidence    | `01_research/RESEARCH_FEASIBILITY.md`      |
| User and product requirements        | `02_product/PRD.md`                        |
| Scientific state/feature definitions | `03_scientific/DATA_SCIENTIFIC_SPEC.md`    |
| Forecast methodology and evaluation  | `04_forecasting/DATA_FORECAST_DESIGN.md`   |
| Technical architecture               | `05_architecture/TECHNICAL_SPEC.md`        |
| Architectural decisions              | `06_decisions/ADR_INDEX.md`                |
| Event and telemetry contracts        | `07_contracts/EVENT_TELEMETRY_CONTRACT.md` |

---

# 17. Current Product Status

**Overall Status:** RESEARCHING

**Current Evidence Position:**

The research supports the feasibility of the underlying operational problem and identifies a credible product direction around telemetry, soil-water state, forecasting, uncertainty, and threshold-risk assessment.

However, several product-defining elements remain unresolved, particularly:

* primary user;
* exact operational decision;
* final state representation;
* threshold semantics;
* forecast horizons;
* alert behaviour;
* acceptable performance;
* operational context.

These must be resolved before treating the product definition as final.

---

# 18. Next Decision Gate

**Next gate:** Establish the product's primary user, operational decision, and minimum useful product behaviour.

After this PRD is accepted, the next specification should define the scientific representation required to support that product:

> **`03_scientific/DATA_SCIENTIFIC_SPEC.md`**

That document should establish the data variables, physical meaning, transformations, state representation, assumptions, and scientific constraints without prematurely dictating the software architecture.
