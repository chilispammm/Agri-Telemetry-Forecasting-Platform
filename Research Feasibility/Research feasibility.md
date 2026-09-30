# Agri Telemetry & Forecasting Platform — Research Feasibility

**Document Authority:** This document synthesizes the initial feasibility research for the Agri Telemetry & Forecasting Platform. Its purpose is to distinguish what external evidence supports, what remains uncertain, what can safely proceed to specification, and what must be validated empirically by this project.

This document does **not** determine the final architecture, forecasting model, dataset, or alert methodology. Those decisions require subsequent experiments and ADRs.

**Status:** RESEARCHING
**Last Updated:** September 29, 2026
**Core Principle:** Build the evidence before building the complexity.

---

## 01. Executive Feasibility Assessment

The initial research supports the **general problem framing**: agricultural telemetry can support temporal monitoring of soil-water conditions, while forecasting and uncertainty estimation can potentially provide earlier indication of an approaching management threshold.

However, the feasibility of this specific system has **not yet been demonstrated**.

Three questions remain central:

1. Can a suitable historical in-situ dataset support reproducible telemetry simulation?
2. Can near-term soil-water trajectories be forecast with useful skill beyond simple baselines?
3. Can forecast uncertainty and deviation detection produce sufficiently reliable threshold-risk signals to justify an operational alert?

The project therefore proceeds from **research-supported concept → empirical data validation → forecasting experiments → architecture validation**.

The research does not justify assuming that a particular dataset, forecasting model, broker, or alert rule will succeed.

---

## 02. Problem Feasibility

**Status:** `[ SUPPORTED BY RESEARCH ]`

Agricultural irrigation decisions are not normally based on an isolated raw soil-moisture reading. Soil-water status is interpreted relative to factors such as root-zone depth, available water-holding capacity, crop development, atmospheric demand, rainfall, irrigation, and management thresholds.

The research therefore supports framing the problem around **soil-water trajectory and threshold risk**, rather than simply predicting the next raw sensor value.

The project's operational framing is:

> Given measured root-zone water status, crop stage, soil properties, irrigation/rainfall inputs, and near-term atmospheric demand, will the field reach a management threshold before the next feasible irrigation opportunity — and with what confidence?

This is an **ultimate product vision**, not yet a validated capability of the system.

### Important limitation

The project may not initially possess observed irrigation events, complete field metadata, or sufficient information to reconstruct actual field-level water balance.

The first experimental question is therefore deliberately narrower:

> Can historical in-situ telemetry support calibrated forecasts of near-term soil-water trajectories and identify meaningful deviation or threshold-crossing risk with useful lead time?

---

## 03. Agricultural / Operational Feasibility

**Status:** `[ SUPPORTED BY RESEARCH ]` for the general decision framework
**Status:** `[ REQUIRES EMPIRICAL VALIDATION ]` for this implementation

Agronomic guidance supports evaluating irrigation through root-zone water availability and depletion rather than treating a single sensor value as a universal indicator of crop stress.

### Relevant concepts

* **Root-zone water status:** The physical state the system ultimately seeks to represent.
* **Available water:** Water available to the crop between relevant soil-water limits.
* **MAD — Management Allowable Depletion:** A configurable management threshold rather than a universal constant.
* **Atmospheric demand:** Conditions influencing crop water use, potentially represented through variables such as ET₀ and VPD.
* **Irrigation opportunity:** The practical window within which an operator can respond.

### What research establishes

The general agronomic logic is defensible.

### What research does not establish

The project cannot yet claim that:

* a particular sensor depth represents the complete root zone;
* a particular numeric MAD value is appropriate;
* a specific forecast horizon is operationally sufficient;
* a USCRN station represents a commercial irrigated field;
* natural precipitation events provide an adequate substitute for observed irrigation events.

These require project-specific evidence.

---

## 04. Scientific Feasibility

**Status:** `[ PLAUSIBLE BUT UNPROVEN ]`

The proposed scientific chain is plausible:

`Observed Telemetry → State / Derived Variables → Temporal Forecast → Predictive Uncertainty → Threshold Assessment`

Potentially useful variables include:

* volumetric soil moisture;
* soil temperature;
* air temperature;
* relative humidity;
* precipitation;
* ET₀;
* VPD;
* temporal lags and rolling statistics;
* depth/profile information.

However, several scientific limitations must remain explicit.

### 4.1 Point sensor ≠ field state

A sensor records a local measurement. It does not automatically represent field-average or root-zone water status.

### 4.2 Depth matters

Measurements at different depths represent different portions of the soil profile and may respond differently to rainfall, evaporation, and plant uptake.

### 4.3 Soil moisture ≠ depletion

Volumetric water content is not itself MAD or root-zone depletion. Converting observations into an agronomic state requires soil and crop assumptions.

### 4.4 ET₀ and VPD are not interchangeable

ET₀ represents standardised reference evapotranspiration demand, while VPD describes the atmospheric vapour-pressure gradient. They may both be useful explanatory variables but represent different physical quantities.

### 4.5 Anomaly ≠ cause

An unexpected soil-moisture change may result from rainfall, irrigation, sensor behaviour, spatial heterogeneity, or another physical process. A statistical deviation alone does not establish causation.

---

## 05. Data Feasibility

**Status:** `[ REQUIRES EMPIRICAL TEST ]`

The leading data candidate is **NOAA USCRN**, but the project has not yet completed the required station-level audit.

The distinction between data types is mandatory.

### 5.1 Observed in-situ telemetry

**Candidate:** NOAA USCRN

Potential advantages:

* in-situ observations;
* soil moisture at multiple depths at applicable stations;
* meteorological observations;
* hourly observations;
* public historical data;
* real measurement noise and missingness.

Required validation:

* station availability;
* soil-moisture depth availability;
* timestamp cadence;
* missingness;
* quality flags;
* variable co-availability;
* period of continuous overlap;
* anomalous values;
* provenance;
* suitability of the selected site for the experimental question.

USCRN is therefore a **candidate primary historical source**, not yet the validated project dataset.

### 5.2 Alternative in-situ networks

Potential alternatives include:

* International Soil Moisture Network (ISMN);
* AmeriFlux sites;
* other openly accessible research-grade agricultural or environmental stations.

These remain alternatives until the candidate USCRN audit is completed.

### 5.3 Reanalysis / modelled data

**Candidates:** ERA5-Land / Open-Meteo access to historical modelled products.

Potential uses:

* supplementary meteorological covariates;
* comparison/reference data;
* gap analysis;
* forecast-input experiments where appropriate.

They must not be represented as equivalent to physical sensor observations.

### 5.4 Satellite retrievals

**Candidate:** NASA SMAP

Potential use:

* broader spatial/contextual comparison;
* comparison between station-scale and coarse-scale soil-moisture behaviour.

Not suitable as a direct substitute for hourly edge telemetry.

### 5.5 Static soil context

**Candidate:** ISRIC SoilGrids

Potential use:

* soil texture/profile context;
* static configuration variables.

It is not telemetry and must not be represented as such.

### 5.6 Synthetic telemetry

The likely simulation pattern is:

`Real Historical Observations → Controlled Perturbation / Fault Injection → Timed Telemetry Events`

This allows the project to preserve real temporal structure while testing:

* packet loss;
* duplicate messages;
* delayed messages;
* out-of-order delivery;
* temporary outages;
* sensor drift;
* abnormal readings;
* reconnect behaviour.

Synthetic events must remain explicitly distinguishable from observed source data.

---

## 06. Forecasting Feasibility

**Status:** `[ REQUIRES EMPIRICAL TEST ]`

Research supports the use of time-series forecasting for soil-moisture-related prediction, but it does not establish which model will provide sufficient skill for this project.

Soil moisture is strongly temporally dependent. Consequently:

> **Persistence must earn its defeat.**

### Mandatory baseline

**Persistence / naive forecast**

For a forecast at horizon `h`:

`ŷ(t+h) = y(t)`

This establishes the minimum benchmark that more complex models must materially improve upon.

### Candidate model ladder

The current experimental ladder is:

1. Persistence
2. Seasonal / climatological naive baseline where appropriate
3. Rolling / EWMA baseline
4. ETS
5. ARIMA / SARIMA
6. SARIMAX / dynamic regression
7. Quantile regression
8. Tree-based regression / boosting
9. Sequence models only if evidence justifies escalation

This is an **experiment sequence**, not a final architecture decision.

### Candidate horizons

Initial candidates:

* native interval / 1h;
* 6h;
* 12h;
* 24h;
* 72h;
* 168h.

These horizons remain open until the data audit and baseline experiment establish what is meaningful.

### Required validation

Forecasting experiments must use:

* chronological train/validation/test separation;
* rolling-origin or walk-forward evaluation;
* an untouched final test period;
* no random timestamp splitting;
* explicit handling of weather-feature availability;
* leakage checks for every exogenous variable.

---

## 07. Forecasting Evaluation

The project must not select a model using one aggregate error metric alone.

### Point forecast metrics

Candidate metrics:

* MAE;
* RMSE;
* bias;
* R² as descriptive context;
* skill relative to persistence.

### Probabilistic metrics

Where probabilistic forecasts are produced:

* prediction-interval coverage;
* interval width;
* pinball loss;
* CRPS or an appropriate equivalent;
* calibration by horizon.

### Operational metrics

The system should additionally evaluate:

* threshold-event detection;
* false-alert burden;
* missed events;
* lead time;
* performance across drying/wetting regimes;
* performance across depths;
* stability across temporal periods.

A model that reduces average RMSE while producing materially worse threshold decisions should not automatically be considered an improvement.

---

## 08. Uncertainty / Prediction-Interval Feasibility

**Status:** `[ REQUIRES EMPIRICAL TEST ]`

Point forecasts alone are insufficient for a risk-oriented system.

The project therefore needs a method for estimating uncertainty around future soil-water states.

Candidate approaches include:

* parametric prediction intervals;
* quantile regression;
* quantile tree-based models;
* conformal forecasting;
* empirical residual-based intervals.

The appropriate method remains open.

### Important statistical constraint

Sequential soil-moisture forecast errors are not guaranteed to be independent.

Therefore:

> A sequence of prediction-interval breaches cannot automatically be assigned a false-alarm probability of `αⁿ`.

Any persistence filter or N-of-M rule must instead be treated as an engineering decision and evaluated empirically.

Required evaluation includes:

* nominal versus empirical coverage;
* interval width;
* residual autocorrelation;
* behaviour during rapid wetting/drying;
* event-level false alerts;
* lead time.

---

## 09. Anomaly / Deviation Feasibility

**Status:** `[ PLAUSIBLE BUT UNPROVEN ]`

The research supports separating several kinds of abnormal behaviour rather than treating every statistical deviation as the same anomaly.

### Proposed taxonomy

#### 1. Data-quality anomaly

Examples:

* missing telemetry;
* impossible values;
* duplicated events;
* prolonged flatline;
* sensor drift;
* timestamp corruption.

#### 2. Model deviation

Observed behaviour differs materially from the model's expected distribution.

#### 3. Physical / environmental deviation

Observed behaviour differs from expected behaviour in a way that may correspond to:

* rainfall;
* drying;
* unusual atmospheric demand;
* sensor placement effects;
* another physical process.

#### 4. Agronomic risk

The forecast indicates a potentially meaningful approach toward a configured management threshold.

#### 5. Operational anomaly

The telemetry or processing pipeline behaves unexpectedly:

* delayed events;
* duplicate events;
* out-of-order events;
* consumer failure;
* stale state.

These categories should not automatically be collapsed into a single alert type.

---

## 10. Alert Persistence / N-of-M Feasibility

**Status:** `[ OPEN / REQUIRES EMPIRICAL TEST ]`

A persistence rule may be useful to prevent transient forecast noise from immediately becoming an operational alert.

For example:

> Alert if the threshold-risk condition is observed in at least `N` of the previous `M` evaluation points.

However, `N` and `M` must not be chosen arbitrarily and presented as statistically validated.

They should be evaluated against:

* false-alert rate;
* missed-event rate;
* alert lead time;
* alert duration;
* serial dependence;
* event severity.

The final rule should be frozen only after validation data are evaluated.

---

## 11. Telemetry Transport Feasibility

**Status:** `[ OPEN QUESTION ]`

The project needs to determine whether the telemetry simulator should communicate using HTTP or MQTT.

### MQTT may be justified if the experiment requires

* persistent device-like connections;
* reconnect behaviour;
* QoS semantics;
* retained state;
* multiple subscribers;
* topic-based routing;
* simulation of constrained or intermittently connected devices.

### HTTP may be sufficient if the workload is simply

`Simulator → Ingestion API → Processing`

with no requirement for broker-mediated delivery or independent consumers.

Therefore MQTT is **not justified merely because the project contains an IoT simulator**.

### Candidate

**MQTT 5 + Mosquitto**

Potential advantages include:

* QoS;
* session semantics;
* retained messages;
* message expiry;
* structured topic hierarchy;
* explicit protocol behaviour around reconnects.

Potential cost:

* another infrastructure component;
* additional operational semantics;
* more failure modes to test.

### Required validation

The transport decision should be based on a concrete workload and tested through scenarios such as:

* normal delivery;
* duplicate delivery;
* disconnect/reconnect;
* delayed delivery;
* publisher interruption;
* consumer interruption;
* message ordering.

---

## 12. Streaming / Buffering Feasibility

**Status:** `[ OPEN QUESTION ]`

If MQTT is selected, the project may require an intermediate durable stream before downstream processing.

Candidate technologies:

* Redis Streams;
* Apache Kafka;
* RabbitMQ;
* direct application processing.

### Redis Streams

Potential fit:

* local Docker Compose deployment;
* relatively small project scale;
* consumer groups;
* pending-entry tracking;
* acknowledgement;
* recovery of unacknowledged messages.

### Kafka

Potential fit where requirements include:

* durable long-lived event logs;
* multiple independent consumer groups;
* substantial replay requirements;
* partition-based scaling;
* larger event volume.

### RabbitMQ

Potential fit where the primary requirement is brokered work queues and routing rather than a durable telemetry history.

### Current position

Redis Streams is a **leading candidate for investigation**, not a final decision.

Kafka is not rejected categorically; it should only be introduced if the workload demonstrates requirements that justify its additional operational complexity.

The final decision requires:

* expected event volume;
* retention requirement;
* replay requirement;
* number of consumers;
* failure-recovery behaviour;
* ordering requirements;
* local resource constraints.

---

## 13. Event Integrity Feasibility

**Status:** `[ SUPPORTED AS AN ENGINEERING REQUIREMENT ]`

Regardless of the transport technology selected, telemetry events require an explicit contract.

Candidate minimum fields:

* `event_id`;
* `device_id`;
* `sensor_id`;
* `field_id`;
* `event_time`;
* `ingest_time`;
* `sequence_number`;
* `schema_version`;
* value;
* unit;
* quality status;
* provenance.

The architecture must distinguish:

**event-time ordering** from **delivery ordering**.

Downstream processing must also be designed around idempotency because at-least-once delivery can produce duplicates.

This requirement is independent of whether MQTT, HTTP, Redis Streams, Kafka, or another transport is eventually selected.

---

## 14. MLOps Feasibility

**Status:** `[ PLAUSIBLE / LIKELY USEFUL — SCOPE OPEN ]`

Experiment tracking is potentially valuable because forecasting experiments will vary by:

* dataset;
* station;
* depth;
* horizon;
* feature set;
* temporal split;
* model;
* hyperparameters;
* preprocessing;
* evaluation metrics.

### MLflow Tracking

Potentially useful for recording:

* experiment parameters;
* metrics;
* tags;
* artifacts;
* model outputs;
* dataset metadata;
* experiment lineage.

### What MLflow does not solve by itself

It does not automatically provide:

* raw-data version control;
* sensor observability;
* data-quality monitoring;
* streaming infrastructure;
* feature stores;
* drift detection;
* retraining policy;
* operational alerting.

### Current scope

MLflow Tracking remains a candidate.

A model registry, automated retraining system, or production-scale MLOps platform should not be introduced unless later requirements justify it.

---

## 15. Architecture Feasibility

**Status:** `[ NOT YET VALIDATED ]`

The architecture cannot be considered validated until the project knows:

1. what data can actually be obtained;
2. what cadence is available;
3. what forecast horizon is useful;
4. what workload the telemetry simulator generates;
5. what delivery guarantees are actually required;
6. what downstream consumers exist;
7. what replay and retention behaviour is necessary.

Therefore the architecture should emerge from the validated workload rather than precede it.

The current conceptual pipeline remains:

`Historical / Simulated Telemetry → Transport → Event Integrity → State Reconstruction → Forecast → Uncertainty → Deviation / Threshold Assessment → Alert`

The implementation technologies inside those stages remain open.

---

## 16. Major Contradictions & Reconciliations

### 16.1 Reanalysis as primary telemetry

**Earlier assumption:** A gap-free weather/reanalysis product could serve as the primary simulated sensor dataset.

**Finding:** This would remove many of the physical and operational properties that the telemetry system is intended to demonstrate.

**Current position:** Reanalysis may be useful as a covariate or reference product, but should not automatically be treated as observed edge telemetry.

**Status:** `[ REJECTED AS PRIMARY TELEMETRY ASSUMPTION ]`

---

### 16.2 Raw soil-moisture deviation as the operational target

**Earlier assumption:** A statistical deviation from expected soil moisture is itself the central anomaly.

**Finding:** A deviation can be caused by legitimate environmental behaviour or sensor conditions and does not automatically represent agronomic risk.

**Current position:** The system should distinguish data-quality, physical/model, and agronomic-risk signals.

**Status:** `[ REJECTED AS SOLE ALERT SEMANTIC ]`

---

### 16.3 Consecutive prediction-interval breaches as independent events

**Earlier assumption:** Repeated breaches could be assigned a simple `αⁿ` probability.

**Finding:** Serial dependence makes the independence assumption inappropriate.

**Current position:** Persistence filters may still be useful, but their behaviour must be empirically evaluated.

**Status:** `[ REJECTED ]`

---

### 16.4 QRF as the predetermined ML solution

**Earlier assumption:** Quantile Random Forest would be the first major ML model.

**Finding:** QRF may be useful for nonlinear and probabilistic prediction, but the project has not yet demonstrated that it outperforms simpler models on the selected dataset.

**Current position:** QRF remains a candidate experiment rather than a predetermined solution.

**Status:** `[ OPEN / REQUIRES EXPERIMENT ]`

---

### 16.5 MQTT as an automatic IoT requirement

**Earlier assumption:** Simulating an ESP32 implies MQTT.

**Finding:** IoT simulation alone does not establish a requirement for MQTT.

**Current position:** MQTT must earn its place through the required transport semantics.

**Status:** `[ OPEN ]`

---

## 17. Research Gaps

The following gaps currently prevent full feasibility validation:

### Data

* suitable station/site not selected;
* actual missingness unknown;
* depth availability unknown;
* quality-flag behaviour not audited;
* continuous overlapping observation period unknown;
* irrigation-event availability unknown.

### Scientific

* target state representation not finalised;
* root-zone reconstruction method not selected;
* soil/crop parameters not established;
* MAD parameterisation not established;
* ET₀ implementation not selected;
* VPD implementation not selected.

### Forecasting

* baseline performance unknown;
* useful horizon unknown;
* exogenous feature value unknown;
* uncertainty method unknown;
* threshold-event performance unknown.

### Engineering

* telemetry event rate unknown;
* failure scenarios not yet quantified;
* transport requirements not yet demonstrated;
* replay/retention requirements unknown;
* number of downstream consumers unknown.

### Operational

* actual decision-maker not yet defined;
* feasible irrigation-action window not established;
* observed irrigation information may be unavailable.

---

## 18. Required Empirical Validation

The next research phase should produce evidence in the following order.

### Experiment 1 — Candidate Station Audit

For one or more candidate USCRN stations:

* retrieve historical data;
* inspect available variables;
* inspect soil-moisture depths;
* quantify missingness;
* inspect quality flags;
* identify continuous periods;
* inspect temporal cadence;
* examine precipitation and soil-moisture response;
* document provenance.

**Output:** Data Feasibility Record.

---

### Experiment 2 — Temporal Characterisation

For the selected target:

* inspect autocorrelation;
* inspect seasonal behaviour;
* identify wetting/drying regimes;
* quantify persistence;
* examine missingness patterns;
* identify candidate forecast horizons.

**Output:** Temporal Baseline Report.

---

### Experiment 3 — Persistence Forecast

Run chronological rolling-origin persistence forecasts.

Evaluate:

* 1h;
* 6h;
* 12h;
* 24h;
* 72h;
* 168h where data support it.

**Output:** Baseline Forecast Report.

This experiment determines whether the forecasting problem is sufficiently difficult to justify escalation.

---

### Experiment 4 — Statistical Escalation

Only if justified by Experiment 3:

* test a transparent statistical model;
* introduce selected exogenous variables;
* compare against persistence;
* evaluate whether improvements are consistent.

**Output:** Model Comparison Report.

---

### Experiment 5 — Probabilistic Forecasting

Evaluate candidate uncertainty methods against:

* empirical coverage;
* interval width;
* calibration;
* event detection;
* lead time.

**Output:** Uncertainty Validation Report.

---

### Experiment 6 — Telemetry Fault Simulation

Only after the historical data contract is stable:

* inject packet loss;
* duplicates;
* delay;
* out-of-order events;
* outages;
* drift;
* anomalous observations.

**Output:** Fault Model / Telemetry Reliability Report.

---

### Experiment 7 — Transport / Streaming Decision

Use the actual workload generated by the previous experiments to compare:

* HTTP;
* MQTT;
* direct processing;
* Redis Streams;
* other candidates only where requirements justify them.

**Output:** ADR evidence.

---

## 19. Decision Gate Status

| Gate                                   | Requirement                                                                               | Status                      | Evidence Required                           |
| :------------------------------------- | :---------------------------------------------------------------------------------------- | :-------------------------- | :------------------------------------------ |
| **1. Problem Feasibility**             | Is the operational problem supported by established agricultural practice and literature? | `[ SUPPORTED BY RESEARCH ]` | Existing agronomic / forecasting literature |
| **2. Data Feasibility**                | Can an appropriate historical in-situ dataset support the experiment?                     | `[ RESEARCHING ]`           | Station audit + EDA                         |
| **3. Forecasting Feasibility**         | Can the target be forecast with useful out-of-sample skill?                               | `[ RESEARCHING ]`           | Persistence + model experiments             |
| **4. Uncertainty / Alert Feasibility** | Can predictive uncertainty support useful event detection?                                | `[ RESEARCHING ]`           | Calibration + event metrics                 |
| **5. Architecture Feasibility**        | Do selected technologies solve demonstrated workload requirements?                        | `[ OPEN ]`                  | Workload + failure/recovery experiments     |
| **6. End-to-End Validation**           | Does the complete system reliably transform telemetry into validated outputs?             | `[ NOT STARTED ]`           | Full integration validation                 |

---

## 20. Definitive Research Status

| Area              | Status                           | What is established                                                           | What remains                           |
| :---------------- | :------------------------------- | :---------------------------------------------------------------------------- | :------------------------------------- |
| Problem           | `[ SUPPORTED BY RESEARCH ]`      | Agricultural water management uses soil-water state and management thresholds | Project-specific operational workflow  |
| Agronomic framing | `[ SUPPORTED / PARTIALLY OPEN ]` | Root-zone status and depletion are meaningful concepts                        | Target representation and parameters   |
| Dataset           | `[ RESEARCHING ]`                | Candidate in-situ networks exist                                              | Station audit                          |
| Forecasting       | `[ RESEARCHING ]`                | Soil-moisture forecasting is technically established                          | Project-specific skill                 |
| Uncertainty       | `[ RESEARCHING ]`                | Probabilistic forecasting is feasible                                         | Calibration on selected data           |
| Anomaly detection | `[ PLAUSIBLE BUT UNPROVEN ]`     | Multiple anomaly categories are meaningful                                    | Event definitions and validation       |
| Transport         | `[ OPEN ]`                       | MQTT and HTTP can support telemetry                                           | Actual workload requirement            |
| Streaming         | `[ OPEN ]`                       | Redis/Kafka/RabbitMQ provide different semantics                              | Retention/replay/consumer requirements |
| MLOps             | `[ PLAUSIBLE ]`                  | Experiment tracking is useful for reproducibility                             | Final scope                            |
| End-to-end system | `[ NOT VALIDATED ]`              | Conceptual pipeline is coherent                                               | Full empirical validation              |

---

## 21. What Research Now Justifies

The project can now safely proceed to specification work for:

* a telemetry-centred temporal system rather than a spatial remote-sensing system;
* an experimental target centred on soil-water trajectory;
* explicit treatment of uncertainty;
* persistence as the mandatory forecasting baseline;
* chronological / walk-forward validation;
* strict separation of observed, modelled, satellite, static, and synthetic data;
* explicit telemetry event integrity;
* fault-injection testing;
* empirical evaluation of threshold-risk detection.

The following should **not** yet be frozen:

* final dataset;
* final soil-water state representation;
* MAD numeric value;
* forecast horizons;
* final feature set;
* final forecasting model;
* uncertainty method;
* N-of-M parameters;
* MQTT versus HTTP;
* Redis Streams versus Kafka/RabbitMQ;
* final MLflow scope;
* observed versus simulated irrigation treatment.

---

## 22. Current Decision

**Current Status:** RESEARCHING

The initial research phase has established that the project has a defensible problem domain and a technically plausible experimental path.

It has **not** yet established that the proposed dataset, forecasting approach, uncertainty method, alert logic, or architecture will work.

Therefore the next decision is deliberately narrow:

> **Audit the candidate NOAA USCRN data before specifying the scientific target or technical architecture.**

The immediate deliverable is a reproducible **candidate station/data audit**.

Only after that evidence exists should the project proceed to the next level of specification.
