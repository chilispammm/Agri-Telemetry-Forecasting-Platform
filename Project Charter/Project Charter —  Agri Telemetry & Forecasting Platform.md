# Agri Telemetry & Forecasting Platform — Project Charter

**Status:** RESEARCHING  
**Last Updated:** September 29, 2026

## Document Authority

This charter defines project intent, boundaries, and evaluation criteria. It does not dictate final architecture. Later specifications (Data/Scientific Spec, PRD, Technical Spec) and Architecture Decision Records (ADRs) will define detailed mathematical, scientific, and technical decisions based on empirical evidence.

## Governing Principles

> **Core Principle:** Build the evidence before building the complexity.
> **Workflow:** PLAN → RESEARCH → SPECIFY → BUILD → TEST → MEASURE → REVIEW → UPDATE

Architecture must be justified by requirements and empirical evidence.

---

## 01. Project Identity & Concept

**Project Name:** Agri Telemetry & Forecasting Platform

**Product Concept:** An operational time-series intelligence system that reconstructs the selected soil-water state from incoming telemetry, forecasts near-term trajectories with uncertainty, and identifies potential threshold risks early enough to support an irrigation decision.

## 02. Problem Statement

Continuous agricultural telemetry can provide the basis for a useful temporal baseline, but a statistical deviation in a raw sensor signal is not inherently actionable. A deviation becomes operationally meaningful only when it changes the probability of crossing a crop- and growth-stage-specific management threshold before the operator can complete an irrigation cycle.

## 03. Central Questions

**Ultimate Operational Vision:**

"Given measured root-zone water status, crop stage, soil properties, irrigation/rainfall inputs, and near-term atmospheric demand, will the field reach a management threshold before the next feasible irrigation opportunity—and with what confidence?"

**Initial Experimental Question:**

"Can historical in-situ telemetry support calibrated forecasts of near-term soil-water trajectories and identify meaningful deviation or threshold-crossing risk with useful lead time?"

## 04. Working Hypothesis

Continuous telemetry can establish a conditional temporal baseline for observed soil-water states. Deviations from this baseline, when combined with temporal forecasting and explicit predictive uncertainty, can provide actionable lead time to evaluate threshold risks under weather uncertainty.

## 05. Target User / Decision-Maker

[ UNKNOWN ] (To be defined in PRD. Examples may include farm operators or agronomists).

## 06. Primary System Objective

Generate probabilistic look-ahead trajectories of the selected soil-water state and assess potential management-threshold risk with quantified uncertainty.

## 07. Scientific Scope

The conversion of raw meteorological and soil telemetry into physical derived variables, feature matrices, and threshold alert outputs based on established water-balance principles (e.g., FAO-56).

## 08. Engineering Scope

The end-to-end pipeline required to simulate, transport, buffer, process, forecast, and log telemetry data reproducibly.

## 09. Explicit Non-Goals / Out of Scope

* Physical hardware deployment.
* Integration with proprietary farm APIs.
* Full-scale UI dashboards (until the API is fully proven).
* Automatic site-crop monitoring and multi-spectral analysis.
* Seasonal or multi-month drought forecasting.
* Assigning a universal numeric value to the MAD threshold.
* Adding Kubernetes, cloud infrastructure, automated retraining, model registries, or deep-learning pipelines unless explicitly required by evidence.

---

## 10. Conceptual Reasoning Flow

*This is the project's reasoning architecture, not a final technical architecture:*

`Telemetry → Data/Event Integrity → State Reconstruction → Forecast → Predictive Uncertainty → Deviation / Threshold Assessment → Operational Risk`

## 11. Core Concepts & Terminology

* **MAD (Management Allowable Depletion):** A configurable agronomic threshold dictating the maximum acceptable root-zone water deficit. Must not be universal/hardcoded.
* **Data-Quality Anomaly:** Sensor malfunction, drift, or communication error.
* **Physical Deviation:** Unexpected drying/wetting (e.g., unrecorded rainfall).
* **Agronomic Risk:** Trajectory indicating an impending MAD breach.
* **Prediction Interval:** Not the same as a confidence interval; used for quantifying predictive uncertainty of a future observation.

## 12. Candidate Inputs & Outputs

* **Observed Inputs:** Volumetric Soil Moisture, Air Temperature, Relative Humidity, Precipitation (USCRN candidate).
* **Open Inputs:** Irrigation events (No observed source has yet been established).
* **Explanatory Covariates:** ET₀, VPD (Researching candidates).
* **Outputs:** Probabilistic depletion forecast, prediction intervals, threshold risk alerts.

## 13. Research-Derived Constraints

* Point measurements do not represent field averages; analysis must be profile-aware.
* Native source cadence will be preserved where possible. An hourly simulation interval is a candidate pending station/data audit.
* Persistence is the mandatory forecasting baseline. Deep learning is deferred.
* Reanalysis data (e.g., ERA5) must not be presented as observed telemetry.
* Synthetic telemetry must remain distinguishable from real observations.
* Walk-forward/chronological validation is required to prevent temporal leakage.
* Repeated breaches cannot be treated as independent events merely because they are consecutive.

## 14. Success Criteria

* Demonstrated ability to detect predefined deviation or threshold-crossing events out-of-sample, with quantified lead time and false-alert burden.
* Reproducible execution in a local Docker Compose environment.

---

## 15. Validation Gates & Status

*Note: Status = project state. Evidence = strength of supporting research.*

| Gate | Requirement | Status | Evidence Assessment |
| :--- | :--- | :--- | :--- |
| **1. Problem Validated** | Is this a meaningful operational problem? | [ RESEARCHING ] | Research strongly supports the operational problem framing. |
| **2. Data Validated** | Requires USCRN station audit (missingness, cadence, co-availability, depth, provenance). | [ RESEARCHING ] | Literature confirms candidate dataset existence; site audit pending. |
| **3. Forecasting Validated** | Requires out-of-sample experiment: Persistence → statistical model → uncertainty/horizon evaluation. | [ RESEARCHING ] | Literature supports feasibility; project experiment pending. |
| **4. Architecture Validated** | Do the proposed technologies solve actual workload requirements? | [ OPEN ] | Awaiting data and workload requirements. |
| **5. End-to-End Validated** | Does the system process telemetry and generate accurate alerts? | [ NOT STARTED ] | N/A |

---

## 16. Deliberately Open Decisions

*These decisions must NOT yet be treated as final. They will be resolved through the research → experiment → ADR process.*

* Primary historical station/site
* Final target/state representation
* Forecast horizons (Candidates: 1h, 6h, 12h, 24h, 72h, 168h)
* Exogenous feature set
* ET₀ / VPD implementation
* Uncertainty method
* Anomaly / deviation method
* MQTT vs HTTP
* Redis Streams vs Kafka / RabbitMQ
* MLflow scope
* Synthetic telemetry fault model
* Alert semantics
* Treatment of irrigation information

## 17. Known Assumptions

* Reliable telemetry reaches the system at a cadence appropriate to the decision.
* Crop identity, growth stage, soil characteristics, and basic weather data are known.
* A manager has a feasible action window before the predicted threshold crossing.

## 18. Major Risks

* *False Alarms via Autocorrelation:* A pointwise prediction interval breach does not provide a sequence-wise false-alarm guarantee.
* *Reanalysis Substitution Error:* Using modelled/reanalysis soil moisture (ERA5-Land) as an exact "ground truth" target prevents the realistic simulation of physical sensor anomalies.
* *Data Leakage:* Randomly distributing timestamps from a weather event across train/test sets leaks future information.

---

## 19. Evidence / Provenance

* **Agronomy:** FAO-56 irrigation guidelines, USDA NRCS standards (CPS 449), UMN/Arizona Extension protocols.
* **Drought/Anomaly Context:** Copernicus C3S metadata, AMS Journals.
* **Forecasting:** ASCE, MDPI, Hydrology and Earth System Sciences peer-reviewed literature.

## 20. Portfolio Capabilities Demonstrated

* Time-Series Forecasting
* Event-Driven Data Processing
* IoT / Edge Concepts
* MLOps & Reproducibility
* Engineering Judgement

## 21. Current Project Status & Next Decision Gate

* **Current Status:** Research feasibility established; empirical data validation is now beginning.
* **Next Decision Gate:** Execute NOAA USCRN (candidate) station audit and EDA to validate Gate 2.