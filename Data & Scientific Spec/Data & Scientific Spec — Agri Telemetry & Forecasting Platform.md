# Agri Telemetry & Forecasting Platform — Data & Scientific Specification

**Status:** RESEARCHING  
**Last Updated:** September 30, 2026  
**Document:** `03_scientific/DATA_SCIENTIFIC_SPEC.md`

---

## 1. Document Authority

This document defines the scientific meaning, structure, provenance, transformation, and interpretation of data used by the Agri Telemetry & Forecasting Platform.

It establishes:

- what constitutes an observation;
- what scientific state the system is attempting to represent;
- which variables are measured versus derived;
- how soil-water state is represented;
- how atmospheric demand, precipitation, and irrigation are treated;
- temporal and unit conventions;
- quality-control and missing-data principles;
- threshold and risk semantics;
- scientific assumptions and limitations;
- validation requirements for unresolved scientific decisions.

This document does **not** define:

- message-broker architecture;
- API architecture;
- database technology;
- deployment topology;
- forecasting model selection;
- MLflow or other MLOps tooling;
- final alert implementation;
- user-interface design.

Those decisions belong to the Technical Specification, Forecast Design, Event/Telemetry Contract, and ADRs.

---

## 2. Governing Scientific Principle

> **Represent the physical state before attempting to predict or classify it.**

The system must not treat a raw sensor reading, statistical anomaly, or model output as an agricultural decision signal without establishing what that quantity represents physically and operationally.

The scientific reasoning chain is:

**OBSERVATION → QUALITY CONTROL → STATE REPRESENTATION → DERIVED VARIABLES → FORECAST → UNCERTAINTY → THRESHOLD/RISK ASSESSMENT**

A technically successful pipeline does not establish scientific validity.

---

## 3. Scientific Objective

The scientific objective is to determine whether historical and simulated agricultural telemetry can support reproducible, uncertainty-aware forecasts of a relevant soil-water state and identify potential threshold-crossing risk with useful lead time.

The primary experimental question remains:

> **Can historical in-situ telemetry support calibrated forecasts of near-term soil-water trajectories and identify meaningful deviation or threshold-crossing risk with useful lead time?**

The system is therefore concerned with **temporal state estimation and forecasting**, rather than simply predicting the next raw sensor reading.

---

## 4. Scientific Object

### 4.1 Primary Scientific Object

The primary scientific object is a **soil-water state observed at a defined location and depth over time**.

The exact state representation remains **RESEARCHING**.

Candidate representations include:

1. volumetric soil-water content;
2. normalised soil-water status;
3. root-zone water storage;
4. root-zone depletion;
5. fraction of available water;
6. another physically justified transformation of observed soil-water content.

No candidate is considered the final target until it has been evaluated against:

- data availability;
- physical interpretability;
- temporal stability;
- forecastability;
- agronomic relevance;
- threshold interpretability;
- cross-site comparability.

### 4.2 Why Raw Soil Moisture May Not Be Sufficient

Volumetric soil-water content is a measurable physical quantity, but the same volumetric value can imply different agronomic conditions depending on:

- soil texture;
- field capacity;
- permanent wilting point;
- soil depth;
- root-zone depth;
- crop;
- crop growth stage;
- rooting distribution;
- sensor calibration;
- local hydraulic conditions.

Therefore:

> **A raw soil-moisture value must not automatically be interpreted as crop water stress or irrigation need.**

---

## 5. Observation Classes

Every important quantity must be classified by origin.

| Class | Definition | Example |
|---|---|---|
| Observed | Directly obtained from an observational dataset or telemetry source | Soil moisture |
| Derived | Calculated from observed or otherwise explicitly sourced variables | ET0, VPD |
| Modelled | Produced by a numerical/reanalysis model | ERA5-Land soil water |
| Forecast | Future estimate available at forecast origin | Weather forecast |
| Simulated | Artificially generated to reproduce telemetry behaviour | Resampled device stream |
| Synthetic Fault | Controlled corruption applied to a simulated stream | Packet loss |
| Predicted | Produced by the project's forecasting model | Soil-water quantile forecast |

These classes must remain distinguishable throughout the pipeline.

A modelled/reanalysis quantity must not be silently relabelled as an observed field measurement.

---

# 6. Candidate Data Sources

## 6.1 Primary Observational Candidate

**NOAA USCRN** remains the leading candidate for the initial empirical study because it provides high-frequency in-situ meteorological and soil observations suitable for temporal forecasting experiments.

Candidate variables include:

- soil moisture;
- soil temperature;
- air temperature;
- relative humidity;
- precipitation;
- solar radiation.

However:

> **USCRN is not yet scientifically validated as the project's final data source.**

A station-level audit is required before the source can move from `RESEARCHING` to `DECIDED`.

The audit must establish:

- station availability;
- observation period;
- soil-moisture depth(s);
- cadence;
- missingness;
- quality flags;
- variable completeness;
- timestamp behaviour;
- continuity;
- suitability of the available soil and atmospheric variables;
- whether the resulting dataset supports the intended forecasting experiment.

## 6.2 Alternative Observational Sources

Potential alternatives include:

- International Soil Moisture Network (ISMN);
- AmeriFlux;
- other suitable public in-situ research networks.

These remain alternatives rather than fallback sources selected in advance.

Selection must be evidence-based.

## 6.3 Reanalysis and Modelled Products

Potential products such as ERA5-Land may provide:

- meteorological covariates;
- atmospheric demand inputs;
- precipitation;
- soil-water context.

They may be useful for historical covariates or comparison.

They must not be treated as equivalent to local in-situ observations.

## 6.4 Satellite Products

Products such as SMAP may provide broader soil-moisture context.

They are not assumed to represent:

- hourly field telemetry;
- local root-zone conditions;
- direct irrigation requirements.

Any use must explicitly account for differences in:

- spatial scale;
- temporal cadence;
- measurement depth;
- retrieval method.

## 6.5 Soil Context

Soil datasets may provide contextual variables such as:

- soil texture;
- soil-water retention characteristics;
- bulk density;
- available water capacity.

These are contextual inputs, not telemetry observations.

---

# 7. Variable Catalogue

The following catalogue defines the current scientific role of candidate variables.

| Variable | Origin | Scientific Role | Unit | Status |
|---|---|---|---|---|
| Volumetric soil moisture | Observed | Primary soil-water observation candidate | m³/m³ | RESEARCHING |
| Soil temperature | Observed | Soil/environmental explanatory variable | °C | RESEARCHING |
| Air temperature | Observed/forecast | Atmospheric demand/explanatory variable | °C | RESEARCHING |
| Relative humidity | Observed/forecast | Atmospheric demand/explanatory variable | % | RESEARCHING |
| Precipitation | Observed/forecast | Water input | mm | RESEARCHING |
| Irrigation | Observed/simulated | Water input | mm or equivalent | OPEN |
| Wind speed | Observed/forecast | ET0 input | m/s | OPEN |
| Solar radiation | Observed/forecast | ET0 input | W/m² or MJ/m²/day | OPEN |
| Net radiation | Derived/observed | ET0 input | energy flux | OPEN |
| VPD | Derived | Atmospheric dryness indicator | kPa | RESEARCHING |
| ET0 | Derived | Reference atmospheric water demand | mm/day | RESEARCHING |
| Root-zone depth | Contextual | State interpretation | mm or m | OPEN |
| Field capacity | Contextual | Water-retention parameter | m³/m³ | OPEN |
| Wilting point | Contextual | Water-retention parameter | m³/m³ | OPEN |
| MAD | Derived/configured | Management threshold | fraction or equivalent | OPEN |

This table is a working scientific catalogue rather than a declaration that every variable will enter the final forecasting model.

---

# 8. Soil-Water State Representation

## 8.1 Volumetric Soil-Water Content

Volumetric soil-water content is expressed as:

\[
\theta_v = \frac{V_{water}}{V_{soil}}
\]

with units of:

\[
m^3/m^3
\]

It is a directly interpretable physical measurement but is not, by itself, a universal measure of crop water stress.

## 8.2 Available Water

Where field capacity and wilting point are available, a normalised representation may be considered:

\[
AW = \theta_{FC} - \theta_{WP}
\]

and:

\[
f_{AW} =
\frac{\theta_v - \theta_{WP}}
{\theta_{FC} - \theta_{WP}}
\]

where:

- \(\theta_v\) = observed volumetric soil-water content;
- \(\theta_{FC}\) = field capacity;
- \(\theta_{WP}\) = permanent wilting point.

This representation is a **candidate**, not a final specification.

Its validity depends on the quality and applicability of the soil-water retention parameters.

## 8.3 Root-Zone Water Storage

If multiple depths and sufficient soil parameters are available, the system may represent water storage across a defined root zone.

Conceptually:

\[
S = \sum_i \theta_i \Delta z_i
\]

where:

- \(\theta_i\) = soil-water content at depth interval \(i\);
- \(\Delta z_i\) = thickness represented by that interval.

A more complete formulation may account for soil-specific properties and rooting distribution.

The project must not imply root-zone conditions from a single shallow sensor without evidence.

## 8.4 Root-Zone Depletion

A depletion representation may be expressed conceptually as:

\[
D = S_{FC} - S
\]

where:

- \(S_{FC}\) = root-zone water storage at the chosen reference field-capacity condition;
- \(S\) = current estimated root-zone storage.

The final formulation remains OPEN.

---

# 9. Sensor Depth

Depth is a first-class scientific attribute.

A soil-moisture observation without depth information is incomplete for root-zone interpretation.

Each soil-water observation should retain:

- measurement depth;
- depth interval where applicable;
- sensor identifier;
- site/station identifier;
- unit;
- timestamp;
- quality flag;
- provenance.

Different depths must not automatically be merged into a single time series.

A shallow sensor and a deeper sensor can legitimately exhibit different temporal responses to:

- rainfall;
- evaporation;
- infiltration;
- root uptake;
- drainage.

---

# 10. Atmospheric Demand

## 10.1 Reference Evapotranspiration (ET0)

ET0 represents atmospheric evaporative demand for a standard reference surface.

Where required variables are available, the project may derive ET0 using an established method such as the FAO-56 Penman-Monteith formulation.

ET0 is considered a candidate explanatory variable because soil-water decline is affected by atmospheric demand.

The exact implementation remains RESEARCHING pending:

- variable availability;
- temporal resolution;
- source consistency;
- missing-data treatment;
- calculation requirements.

## 10.2 Vapour Pressure Deficit (VPD)

VPD describes the atmospheric moisture deficit and may provide explanatory information about atmospheric dryness.

It is not equivalent to ET0.

The system must not substitute VPD for ET0 merely because VPD is easier to calculate.

VPD may be derived from temperature and humidity using an explicitly documented formulation.

Its final role is OPEN.

## 10.3 Scientific Distinction

The project distinguishes:

**VPD → atmospheric moisture deficit**

from:

**ET0 → reference-surface evaporative demand**

Both may be informative, but their scientific meanings differ.

---

# 11. Rainfall and Irrigation

## 11.1 Rainfall

Rainfall is treated as a water input rather than simply another predictor.

The system must preserve:

- observation time;
- accumulation period;
- measurement unit;
- source;
- quality/provenance.

Temporal aggregation must account for the fact that rainfall is an accumulated quantity.

For example, summing precipitation across an interval is fundamentally different from averaging soil moisture across that interval.

## 11.2 Irrigation

Actual irrigation events are currently an important data gap.

The scientific specification therefore does not assume that irrigation history exists in the primary observational dataset.

Potential approaches include:

1. use a dataset/site containing observed irrigation;
2. exclude irrigation-dependent analyses where irrigation cannot be observed;
3. introduce explicitly labelled simulated irrigation events;
4. use an intervention/scheduling layer as an experimental assumption.

The final approach must be documented rather than silently inferred.

A simulated irrigation event must never be represented as an observed farm event.

---

# 12. Temporal Representation

## 12.1 Event Time

The timestamp associated with when an observation occurred is the primary scientific time reference.

## 12.2 Ingestion Time

The timestamp associated with when the system received an event is operational metadata.

The two must remain distinct.

A delayed event must not be treated as a newly observed physical event simply because it was received later.

## 12.3 Native Cadence

Where possible, source observations should be retained at their native cadence before aggregation.

The system must not manufacture higher-frequency physical observations merely to satisfy a streaming architecture.

For example:

> Hourly observed soil moisture must not be presented as genuine five-minute soil-moisture observations simply because the simulated edge device publishes every five minutes.

A five-minute simulated stream may repeat, transform, or perturb the historical signal for event-processing experiments, but it must remain labelled as simulated.

---

# 13. Temporal Aggregation

Aggregation must be variable-specific.

Examples:

| Variable Type | Candidate Aggregation |
|---|---|
| Soil moisture | Mean / median / selected state representation |
| Temperature | Mean / min / max |
| Relative humidity | Mean / selected statistics |
| Precipitation | Sum |
| Solar radiation | Integrated/aggregated energy |
| Wind speed | Mean / distributional statistics |
| ET0 | Sum over relevant forecast period |
| VPD | Mean / max / distributional statistics |

These are candidate rules and must be validated against the forecasting task.

Aggregation must not use future observations relative to a forecast origin.

---

# 14. Data Quality

Data quality is a scientific concern, not merely an engineering concern.

The system must distinguish between:

1. missing observation;
2. explicitly flagged poor-quality observation;
3. physically implausible observation;
4. duplicate observation;
5. delayed observation;
6. out-of-order observation;
7. sensor drift;
8. communication outage;
9. genuine environmental extreme.

These categories must not automatically be collapsed into a single `anomaly` label.

## 14.1 Quality Flags

Source-provided quality flags must be preserved where available.

The project should not overwrite the original quality classification without retaining the source value.

## 14.2 Missingness

Missing data must be quantified before modelling.

Required audit dimensions include:

- overall missingness;
- missingness by variable;
- missingness by station;
- missingness by depth;
- missingness by season;
- consecutive missing periods;
- relationship between missingness and environmental conditions where testable.

## 14.3 Imputation

Imputation is not automatically permitted.

Any imputation used for forecasting must:

- be defined explicitly;
- avoid future leakage;
- be applied consistently across evaluation periods;
- preserve the distinction between observed and imputed values;
- be evaluated for its effect on forecast performance.

---

# 15. Physical Plausibility

Physical plausibility checks may be used to identify candidate data-quality problems.

Examples include:

- impossible units;
- impossible timestamps;
- impossible precipitation values;
- abrupt sensor changes inconsistent with neighbouring observations;
- persistent flatlining;
- unrealistic jumps;
- physically implausible soil-moisture ranges.

However:

> **A statistically unusual observation is not automatically physically incorrect.**

Extreme weather and genuine environmental transitions can produce unusual measurements.

Data-quality rules must therefore be conservative and traceable.

---

# 16. Derived Variables

Derived variables must retain their calculation provenance.

At minimum, derived-variable metadata should identify:

- source variables;
- calculation method;
- parameter values;
- temporal resolution;
- unit;
- software/code version where relevant;
- assumptions.

Candidate derived variables include:

- VPD;
- ET0;
- rolling soil-moisture change;
- rate of drying/wetting;
- cumulative precipitation;
- estimated depletion;
- available-water fraction.

A derived variable must not be presented as an independently observed measurement.

---

# 17. Soil-Water Balance Concepts

The scientific framework recognises the conceptual water balance:

\[
\Delta S =
P + I + CR - ET - R - DP
\]

where:

- \(\Delta S\) = change in soil-water storage;
- \(P\) = precipitation;
- \(I\) = irrigation;
- \(CR\) = capillary rise;
- \(ET\) = evapotranspiration;
- \(R\) = runoff;
- \(DP\) = deep percolation.

The project does not currently claim that all terms can be observed or estimated reliably.

This equation provides a physical framework for interpreting soil-water trajectories rather than an assertion that the final system will implement a complete water-balance model.

---

# 18. Management Allowable Depletion (MAD)

MAD is treated as a **management parameter**, not a universal physical constant.

Conceptually, irrigation may be initiated before the soil-water deficit reaches a chosen maximum allowable depletion.

The appropriate value depends on factors including:

- crop;
- crop growth stage;
- soil water-holding characteristics;
- effective rooting depth;
- irrigation system;
- management objective;
- expected atmospheric demand;
- operational constraints.

Therefore:

> **The project must not hard-code a universal MAD value such as 20% without scientific and project-specific justification.**

The final threshold representation remains OPEN.

Possible forms include:

- fraction of available water depleted;
- volumetric soil-water threshold;
- root-zone storage threshold;
- crop-stage-specific threshold;
- another scientifically justified state threshold.

---

# 19. Threshold Semantics

A threshold must be defined against the chosen state representation.

For example:

**Observed state → estimated depletion → management threshold**

is scientifically different from:

**raw sensor reading → arbitrary numeric cutoff**

Threshold selection must therefore occur only after the state representation has been established.

Thresholds must document:

- physical meaning;
- units;
- source/evidence;
- applicable crop/stage/soil context;
- whether the threshold is observed, derived, or configured;
- uncertainty;
- operational interpretation.

---

# 20. Deviation Semantics

The system distinguishes several forms of deviation.

## 20.1 Data-Quality Deviation

The observation is inconsistent with expected data behaviour.

Examples:

- duplicate event;
- impossible value;
- sensor flatline;
- communication gap.

This does not imply environmental change.

## 20.2 Physical/Environmental Deviation

The observed state differs materially from the expected temporal or physical pattern.

Examples may include:

- unusually rapid drying;
- unexpected wetting;
- unexpected persistence after rainfall.

This does not automatically imply crop stress.

## 20.3 Forecast Deviation

The observed trajectory begins to diverge from the forecast distribution.

This is a model-monitoring concept and must be evaluated against the model's uncertainty.

## 20.4 Agronomic/Operational Risk

A forecasted or estimated state approaches a scientifically justified management threshold with sufficient evidence and relevant lead time.

This is the closest level to an operational alert.

The project must not collapse all four categories into one generic anomaly label.

---

# 21. Uncertainty

The project distinguishes:

### Prediction uncertainty

Uncertainty about a future observation or state conditional on available information.

Examples:

- prediction intervals;
- quantile forecasts;
- predictive distributions.

### Measurement uncertainty

Uncertainty associated with the observation itself.

Examples:

- sensor accuracy;
- calibration;
- measurement noise.

### Parameter/model uncertainty

Uncertainty associated with model parameters or model structure.

The project does not currently commit to a single uncertainty decomposition.

Any probabilistic forecast must clearly state what uncertainty its interval or distribution represents.

A prediction interval must not be labelled a confidence interval unless its statistical interpretation genuinely matches that terminology.

---

# 22. Scientific Interpretation of Alerts

An alert should answer a scientifically interpretable question.

A potential alert may contain:

- current observed state;
- expected state;
- forecast trajectory;
- uncertainty bounds;
- relevant threshold;
- estimated time to threshold;
- forecast horizon;
- data-quality status;
- contributing environmental context;
- provenance;
- confidence/calibration information where justified.

The alert must not claim:

> “The crop is stressed.”

unless the project has independent evidence capable of supporting such a claim.

The more defensible statement is closer to:

> “The forecasted soil-water trajectory has a defined probability of approaching/crossing the selected management threshold within the evaluated horizon.”

The exact alert language remains a product/interface decision.

---

# 23. Point Sensor vs Field Representation

A sensor provides a measurement at a specific location and depth.

Therefore:

> **Point telemetry must not automatically be interpreted as field-wide soil-water state.**

Field-level claims require evidence concerning:

- sensor placement;
- spatial variability;
- number of sensors;
- soil heterogeneity;
- irrigation uniformity;
- crop variability;
- representative sampling.

The initial project may therefore operate explicitly at the **station/site/depth** level.

Spatial generalisation is an open validation question rather than an assumption.

---

# 24. Synthetic Telemetry

Synthetic telemetry exists to evaluate event-processing and operational robustness.

The preferred approach is:

**real observed history → controlled transformation → simulated telemetry**

rather than arbitrary random sensor values.

Synthetic experiments may introduce:

- packet loss;
- duplicate delivery;
- delayed delivery;
- out-of-order delivery;
- reconnects;
- sensor drift;
- abnormal readings;
- communication outages.

Synthetic faults must be explicitly labelled.

The scientific forecasting dataset and the synthetic event-processing stream must remain distinguishable.

---

# 25. Scientific Assumptions

Current working assumptions:

1. The selected observational source contains sufficient soil-water observations for temporal analysis.
2. Measurement depth can be identified.
3. Relevant timestamps can be interpreted consistently.
4. At least some atmospheric explanatory variables are available.
5. Soil-water observations retain sufficient temporal structure for forecasting experiments.
6. A scientifically interpretable state representation can be constructed from available data.
7. A management threshold can be defined for the selected experimental context.
8. Forecast evaluation can be performed without future information leakage.
9. Synthetic telemetry can preserve meaningful historical temporal structure.
10. Any irrigation representation not directly observed can be explicitly modelled as an assumption.

Each assumption must be tested where practical.

---

# 26. Known Scientific Limitations

The project currently recognises the following limitations:

### 26.1 Sensor representativeness

A point measurement may not represent the surrounding field.

### 26.2 Missing irrigation observations

Without observed irrigation events, complete operational water-balance reconstruction may not be possible.

### 26.3 Soil parameter uncertainty

Field capacity, wilting point, and available water capacity may be uncertain or unavailable at the required spatial scale.

### 26.4 Root-zone uncertainty

Effective rooting depth changes with crop and growth stage.

### 26.5 Weather forecast uncertainty

Operational forecasts depend on the quality of future weather information.

### 26.6 Sensor error and drift

Observed changes may reflect instrumentation behaviour rather than environmental processes.

### 26.7 Site specificity

A successful model at one station does not establish generalisation to another site, crop, soil, or climate.

### 26.8 Threshold uncertainty

Management thresholds are contextual and may not be precisely known.

### 26.9 Observational limitations

Public research datasets may represent monitoring or climate objectives rather than commercial irrigation operations.

---

# 27. Scientific Validation Requirements

The following must be established before the corresponding decisions can be marked `VALIDATED`.

| Decision | Required Evidence | Status |
|---|---|---|
| Primary observational source | Station/site audit | RESEARCHING |
| Soil-moisture target | Empirical + physical comparison of candidate representations | RESEARCHING |
| Sensor depth selection | Data availability + scientific interpretation | RESEARCHING |
| Forecast horizons | Out-of-sample performance by horizon | RESEARCHING |
| ET0 inclusion | Data availability + ablation/evaluation | RESEARCHING |
| VPD inclusion | Data availability + ablation/evaluation | RESEARCHING |
| State transformation | Forecastability + interpretability evaluation | RESEARCHING |
| MAD representation | Scientific source + project context | OPEN |
| Threshold-crossing definition | Explicit state + threshold formulation | OPEN |
| Deviation method | Empirical detection evaluation | OPEN |
| Alert persistence rule | False-alert/lead-time evaluation | OPEN |
| Spatial generalisation | Multi-site evidence where possible | OPEN |

---

# 28. Required Empirical Experiments

The following experiments are required or strongly expected before major scientific decisions are frozen.

## Experiment A — Source Audit

For each candidate station/site:

- observation period;
- cadence;
- variables;
- depth;
- missingness;
- quality flags;
- timestamp continuity;
- anomalous periods;
- usable modelling period.

## Experiment B — Soil-State Representation

Compare candidate targets such as:

- raw volumetric soil moisture;
- normalised available-water state;
- depletion;
- root-zone representation where feasible.

Evaluate:

- interpretability;
- stability;
- data requirements;
- forecastability;
- threshold compatibility.

## Experiment C — Forecastability

Evaluate persistence before more complex models.

At minimum, investigate candidate horizons including:

- native cadence;
- short horizon;
- 24h;
- 72h;
- 168h.

Final horizons remain evidence-dependent.

## Experiment D — Feature Value

Evaluate candidate inputs such as:

- precipitation;
- temperature;
- humidity;
- ET0;
- VPD;
- lagged soil moisture;
- temporal features.

Feature inclusion must be supported by out-of-sample evidence.

## Experiment E — Threshold Risk

Where a defensible threshold is available, evaluate:

- threshold-crossing detection;
- lead time;
- missed events;
- false alerts;
- uncertainty calibration.

## Experiment F — Synthetic Telemetry

Evaluate event-processing behaviour under:

- duplicates;
- delays;
- out-of-order events;
- missing events;
- reconnects;
- abnormal readings.

This validates engineering behaviour rather than agricultural forecasting validity.

---

# 29. Scientific Rejection Criteria

A proposed scientific approach should be rejected or reconsidered if:

- it requires unavailable data to function;
- it treats modelled data as observed without justification;
- it depends on future information;
- it produces strong agricultural claims from weak measurements;
- it requires an arbitrary universal threshold;
- it materially worsens calibration or event performance;
- it only performs well under random temporal splits;
- it cannot be reproduced;
- its additional complexity produces no meaningful scientific or operational benefit.

---

# 30. Open Scientific Decisions

The following remain deliberately unresolved:

1. Primary observational dataset/site.
2. Final soil-water state representation.
3. Primary sensor depth.
4. Whether the model target should be raw soil moisture or a transformed state.
5. Root-zone representation.
6. ET0 calculation method.
7. Whether VPD materially improves forecasting.
8. Treatment of irrigation.
9. Forecast horizons.
10. Forecast uncertainty method.
11. Threshold representation.
12. MAD definition.
13. Deviation detection method.
14. Alert persistence/confirmation rule.
15. Required spatial generalisation.
16. Minimum evidence required for agronomic risk classification.

These decisions should be resolved through evidence rather than preference.

---

# 31. Scientific Decision Status

| Area | Status |
|---|---|
| Agricultural problem framing | RESEARCHING |
| Observational data source | RESEARCHING |
| Soil-water target | RESEARCHING |
| Soil depth | RESEARCHING |
| Root-zone representation | OPEN |
| ET0 | RESEARCHING |
| VPD | RESEARCHING |
| Rainfall treatment | RESEARCHING |
| Irrigation treatment | OPEN |
| Forecast horizons | RESEARCHING |
| Uncertainty representation | RESEARCHING |
| MAD | OPEN |
| Threshold semantics | OPEN |
| Deviation detection | OPEN |
| Alert persistence | OPEN |
| Spatial generalisation | OPEN |

---

# 32. Traceability

This specification derives its scientific requirements from:

- `00_project/PROJECT_CHARTER.md`
- `01_research/RESEARCH_FEASIBILITY.md`
- `02_product/PRD.md`

It informs:

- `04_forecasting/DATA_FORECAST_DESIGN.md`
- `05_architecture/TECHNICAL_SPEC.md`
- `06_decisions/ADR_INDEX.md`
- `07_contracts/EVENT_TELEMETRY_CONTRACT.md`
- `08_implementation/IMPLEMENTATION_PLAN.md`

Scientific decisions must remain traceable to evidence and, where material, to the corresponding ADR or experiment record.

---

# 33. Current Status

**Overall Status: RESEARCHING**

The project has sufficient scientific framing to begin empirical data investigation.

However, the following have **not** yet been established:

- final observational source;
- final soil-water state;
- final forecast target;
- final feature set;
- final threshold representation;
- final MAD formulation;
- final forecast horizons;
- final deviation methodology;
- final alert semantics.

The purpose of the next stage is therefore not to make these choices by assumption, but to generate the evidence required to make them.

---

## 34. Next Gate

### Gate: Scientific Representation

The next evidence required is:

1. audit candidate observational data;
2. inspect available soil-moisture depths;
3. quantify missingness and quality;
4. examine temporal structure;
5. compare candidate state representations;
6. establish which variables can be computed reliably;
7. identify the minimum scientifically defensible forecasting target.

### Immediate Next Activity

**NOAA USCRN candidate station audit + exploratory data analysis.**

The result of that audit should update this document and determine which scientific decisions can move from:

**RESEARCHING → DECIDED**

without prematurely locking the architecture or forecasting model.