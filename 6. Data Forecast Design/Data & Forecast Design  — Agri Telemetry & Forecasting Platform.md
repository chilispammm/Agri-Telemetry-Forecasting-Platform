# Agri Telemetry & Forecasting Platform — Data & Forecast Design

**Status:** RESEARCHING  
**Last Updated:** September 30, 2026  
**Document:** `04_forecasting/DATA_FORECAST_DESIGN.md`

---

## 1. Document Authority

This document defines the forecasting problem, target construction, forecast horizons, information availability, baselines, candidate model classes, validation methodology, uncertainty evaluation, and decision criteria for the Agri Telemetry & Forecasting Platform.

It translates the scientific representation defined in:

- `00_project/PROJECT_CHARTER.md`
- `01_research/RESEARCH_FEASIBILITY.md`
- `02_product/PRD.md`
- `03_scientific/DATA_SCIENTIFIC_SPEC.md`

into a reproducible forecasting specification.

This document does **not** permanently select:

- a specific forecasting model;
- a specific machine-learning library;
- a production serving architecture;
- a message broker;
- a database;
- an MLOps platform.

Those choices remain subject to empirical evidence and, where architectural, ADRs.

---

# 2. Governing Forecasting Principle

> **Persistence must earn its defeat.**

The system must first establish how difficult the forecasting problem actually is.

A more complex model is justified only when it produces a meaningful and reproducible improvement over appropriate simpler baselines under a leakage-safe evaluation.

The objective is therefore not:

> "Build the most sophisticated forecasting model."

It is:

> **"Determine whether additional modelling complexity produces useful predictive and operational value beyond what the temporal structure already provides."**

---

# 3. Forecasting Objective

The forecasting system should estimate the future trajectory of the selected soil-water state from information available at a defined forecast origin.

Conceptually:

\[
\hat{Y}_{t+h|t}
\]

where:

- \(Y\) = selected soil-water state;
- \(t\) = forecast origin;
- \(h\) = forecast horizon;
- \(\hat{Y}_{t+h|t}\) = forecast made at time \(t\) for time \(t+h\).

Where probabilistic forecasting is used, the system should estimate a conditional distribution:

\[
P(Y_{t+h} \mid X_{\leq t})
\]

rather than only a point estimate.

The final target \(Y\) remains dependent on the outcome of the Scientific Specification and empirical target-selection experiments.

---

# 4. Forecast Target

## 4.1 Candidate Targets

The forecasting target may be one of:

1. volumetric soil moisture;
2. normalised available-water state;
3. root-zone storage;
4. root-zone depletion;
5. another scientifically justified state representation.

The target must be selected using evidence from:

- physical interpretability;
- data availability;
- measurement quality;
- temporal stability;
- forecastability;
- threshold compatibility;
- operational relevance.

The project must not select a target merely because it is easiest to model.

## 4.2 Target Definition

Once selected, the target specification must define:

- variable name;
- physical meaning;
- unit;
- sensor depth or root-zone definition;
- aggregation;
- transformation;
- missing-data policy;
- source;
- quality-control policy.

Example:

```text
Target:
    soil_water_state

Definition:
    [to be determined]

Unit:
    [to be determined]

Depth:
    [to be determined]

Cadence:
    [to be determined]

Transformation:
    [to be determined]
````

This section remains intentionally unresolved until the empirical data audit.

---

# 5. Forecast Origin

Every forecast must have an explicit origin time.

At forecast origin \(t\), the model may only use information that would have been available at or before \(t\).

This includes:

* observed historical target values;
* previously observed weather;
* previously derived variables;
* historical static/contextual information;
* genuinely available forecast information;
* known future information where scientifically legitimate.

It must not use:

* future observations;
* future aggregates containing the target period;
* future-imputed values;
* future-derived statistics;
* information generated using the test period;
* features whose availability would not have been known operationally.

---

# 6. Information-Availability Principle

Each feature must have an explicit availability status at forecast origin.

| Information                                     | Available at origin? | Permitted? |
| ----------------------------------------------- | -------------------: | ---------: |
| Historical soil moisture                        |                  Yes |        Yes |
| Historical rainfall                             |                  Yes |        Yes |
| Historical ET0                                  |                  Yes |        Yes |
| Historical VPD                                  |                  Yes |        Yes |
| Soil-moisture value at \(t+h\)                  |                   No |         No |
| Observed rainfall at \(t+h\)                    |                   No |         No |
| Future weather forecast issued at \(t\)         |                  Yes |        Yes |
| Future realised weather                         |                   No |         No |
| Static soil properties                          |                  Yes |        Yes |
| Crop stage known at \(t\)                       |          Potentially |        Yes |
| Crop stage determined using future observations |                   No |         No |

This distinction is critical.

A model that uses future realised weather may be useful as an **oracle/explanatory experiment**, but it must not be presented as an operational forecast.

---

# 7. Forecast Scenarios

To distinguish scientific capability from operational capability, forecasting experiments should separate three information scenarios.

## 7.1 Scenario A — Autoregressive Only

Uses historical target information.

Example:

$$
Y_t, Y_{t-1}, ..., Y_{t-k}
$$

Purpose:

* establish temporal predictability;
* test persistence;
* determine how much information exists in the target itself.

## 7.2 Scenario B — Oracle Exogenous

Uses historical target data plus future realised exogenous variables.

Examples:

* realised future precipitation;
* realised future temperature;
* realised future ET0.

This scenario is **not an operational forecast**.

It is useful for answering:

> "How much forecast skill could the model obtain if future explanatory variables were known perfectly?"

## 7.3 Scenario C — Operational Exogenous

Uses only information that would genuinely be available at forecast origin.

For example:

* historical observations;
* known static variables;
* weather forecasts issued at or before the forecast origin.

This is the scenario that should be used for operational claims.

The project must not report Scenario B performance as though it represents Scenario C.

---

# 8. Forecast Horizons

Candidate horizons are:

* native observation interval;
* 1 hour;
* 6 hours;
* 12 hours;
* 24 hours;
* 72 hours;
* 168 hours / 7 days.

These are candidates, not validated requirements.

The final horizon set must be determined by:

* source cadence;
* target dynamics;
* persistence skill;
* forecast degradation;
* operational decision window;
* availability of future exogenous information.

A horizon should not be included simply because it demonstrates that the model can produce a number.

## 8.1 Horizon-Specific Evaluation

Performance must be reported separately for each horizon.

A model that performs well at 1 hour but poorly at 72 hours must not be described simply as a "good forecaster."

---

# 9. Forecast Types

The system distinguishes:

## 9.1 Point Forecast

A single expected or central estimate:

$$
\hat{Y}_{t+h|t}
$$

Useful for:

* error benchmarking;
* trajectory visualisation;
* baseline comparison.

## 9.2 Probabilistic Forecast

A representation of uncertainty around the expected future state.

Possible representations include:

* prediction intervals;
* quantile forecasts;
* predictive distributions.

The final approach remains OPEN.

## 9.3 Trajectory Forecast

A sequence of predictions across multiple future horizons:

$$
\{\hat{Y}_{t+1|t}, \hat{Y}_{t+2|t}, ..., \hat{Y}_{t+H|t}\}
$$

This is important because the operational objective concerns trajectory and threshold crossing rather than one isolated future value.

---

# 10. Required Baselines

## 10.1 Persistence

Persistence is mandatory.

For horizon \(h\):

$$
\hat{Y}_{t+h|t} = Y_t
$$

This establishes how difficult the forecasting problem is under temporal persistence.

Persistence should not be treated as a trivial baseline.

For highly autocorrelated environmental signals, persistence can be difficult to beat at short horizons.

## 10.2 Seasonal/Climatological Baseline

Where sufficient historical data exists, a second baseline may represent expected conditions for comparable temporal periods.

Potential formulations include:

* seasonal mean;
* historical median;
* climatological quantile;
* comparable-hour/day statistics.

The appropriate formulation depends on the source and record length.

## 10.3 Rolling/EWMA Baseline

A smoothed recent-history baseline may be evaluated.

Examples:

* rolling mean;
* exponentially weighted moving average.

This baseline is optional and must earn inclusion through relevance.

## 10.4 Statistical Baselines

Candidate models include:

* ETS;
* ARIMA;
* SARIMA;
* SARIMAX/dynamic regression.

These models provide interpretable comparisons before more complex machine-learning approaches are considered.

---

# 11. Candidate Machine-Learning Models

Candidate models may include:

* linear/regularised regression;
* quantile regression;
* random forest;
* gradient-boosted trees;
* quantile random forest;
* other tree-based probabilistic approaches.

Model selection must be empirical.

The project should prefer a model that provides sufficient predictive and operational value with lower complexity over a more complex model producing marginal gains.

---

# 12. Deep Learning

Potential sequence models include:

* LSTM;
* GRU;
* temporal convolutional models;
* transformer-based temporal models.

These are explicitly deferred.

Deep learning should only be introduced if evidence shows that:

* simpler models leave material predictive structure unexplained;
* sufficient data exists;
* gains are consistent across evaluation periods/sites;
* gains extend beyond average error;
* uncertainty performance is competitive;
* operational value justifies additional complexity.

Deep learning must not be included merely to demonstrate AI/ML breadth.

---

# 13. Feature Design

Potential feature groups include:

### Target history

* lagged target;
* rolling statistics;
* rate of change;
* recent drying/wetting trend.

### Precipitation

* recent rainfall;
* cumulative rainfall;
* time since rainfall;
* rainfall intensity where supported.

### Atmospheric state

* temperature;
* relative humidity;
* VPD;
* ET0;
* wind;
* radiation.

### Temporal features

* hour;
* day of year;
* season;
* cyclic temporal representations where justified.

### Contextual variables

* soil properties;
* sensor depth;
* crop/stage information where available.

Feature inclusion must be justified by:

1. scientific relevance;
2. availability at forecast origin;
3. data quality;
4. empirical predictive value.

---

# 14. Feature Availability Contract

Every feature used by a forecasting model must have a documented availability definition.

For each feature:

| Feature          | Source          | Available at origin | Lag     | Aggregation | Status      |
| ---------------- | --------------- | ------------------: | ------- | ----------- | ----------- |
| Soil moisture    | Observation     |                 Yes | Defined | Defined     | RESEARCHING |
| Rainfall         | Observation     |                 Yes | Defined | Defined     | RESEARCHING |
| ET0              | Derived         |   Yes if historical | Defined | Defined     | RESEARCHING |
| VPD              | Derived         |   Yes if historical | Defined | Defined     | RESEARCHING |
| Future rainfall  | Observation     |                  No | N/A     | N/A         | PROHIBITED  |
| Weather forecast | Forecast source |         Potentially | Defined | Defined     | OPEN        |

This table must be completed before a model is considered operationally evaluated.

---

# 15. Leakage Prevention

Temporal leakage is a first-order scientific risk.

Potential leakage sources include:

* random train/test splitting;
* future rolling statistics;
* future interpolation;
* future imputation;
* scaling fitted on the full dataset;
* feature engineering using future observations;
* threshold selection using the final test period;
* hyperparameter tuning against the final test set;
* selecting a model after inspecting final test performance;
* using realised future weather in an operational experiment.

All preprocessing required for forecasting must respect the temporal split.

---

# 16. Dataset Splitting

The default evaluation structure is chronological.

Conceptually:

```text
EARLIER HISTORY          VALIDATION             FINAL TEST
──────────────────       ───────────────        ─────────────
Model development        Model selection        Final evaluation
```

The final test period must remain untouched until model selection is complete.

The exact dates depend on the selected dataset and must be documented after the data audit.

---

# 17. Walk-Forward Evaluation

Forecast performance should be evaluated using rolling-origin or walk-forward procedures where practical.

Conceptually:

```text
Train ────────► Forecast
Train ───────────────► Forecast
Train ─────────────────────► Forecast
Train ─────────────────────────────► Forecast
```

The model repeatedly forecasts future observations from historically available information.

This better represents deployment than random temporal splits.

---

# 18. Event-Aware Validation

Environmental events can create leakage or overly optimistic evaluation if split incorrectly.

Examples:

* rainfall events;
* prolonged dry periods;
* irrigation events;
* sensor outages;
* abrupt weather transitions.

Where practical, major contiguous events should not be artificially divided between training and test periods in a way that allows the model to learn the same event pattern on both sides.

The exact event-blocking strategy remains dependent on the dataset.

---

# 19. Multi-Site Validation

If multiple suitable sites/stations are available, evaluation should distinguish:

### Temporal generalisation

Train and test on different periods at the same site.

### Spatial generalisation

Train on some sites and evaluate on an unseen site.

A model performing well temporally at one station has not demonstrated spatial generalisation.

Multi-site validation is therefore desirable but not mandatory if the available data cannot support it.

---

# 20. Point-Forecast Metrics

Candidate point metrics include:

### Mean Absolute Error

$$
MAE =
\frac{1}{n}
\sum_{i=1}^{n}
|y_i-\hat{y}_i|
$$

### Root Mean Squared Error

$$
RMSE =
\sqrt{
\frac{1}{n}
\sum_{i=1}^{n}
(y_i-\hat{y}_i)^2
}
$$

### Mean Bias Error

$$
MBE =
\frac{1}{n}
\sum_{i=1}^{n}
(\hat{y}_i-y_i)
$$

Bias is important because a model may have acceptable average error while systematically over- or under-predicting the state.

### Skill Relative to Persistence

A model should also be evaluated relative to the mandatory persistence baseline.

For example:

$$
Skill =
1 -
\frac{Error_{model}}
{Error_{persistence}}
$$

The exact metric and interpretation must be documented consistently.

---

# 21. Metrics That Require Caution

## R²

R² may be reported descriptively but must not be treated as sufficient evidence of forecasting usefulness.

A high R² can coexist with:

* poor calibration;
* systematic bias;
* poor threshold detection;
* poor long-horizon performance.

Therefore R² is not a primary acceptance criterion.

---

# 22. Probabilistic Forecast Evaluation

If the system produces prediction intervals or quantiles, they must be evaluated directly.

Candidate metrics include:

* empirical coverage;
* interval width;
* pinball loss;
* CRPS;
* weighted interval score (WIS).

## 22.1 Coverage

For a nominal \(1-\alpha\) interval:

$$
P(L_t \leq Y_t \leq U_t)
$$

should be compared with the nominal coverage.

For example, a nominal 90% interval should be evaluated for empirical coverage close to 90%, subject to sampling uncertainty.

## 22.2 Sharpness

A narrow interval is useful only if it remains appropriately calibrated.

Therefore the objective is not:

> "Make the interval as narrow as possible."

It is:

> **"Produce intervals that are sufficiently sharp while maintaining appropriate empirical coverage."**

---

# 23. Threshold/Event Metrics

Because the operational objective concerns threshold risk, average forecast error is not sufficient.

Where a scientifically defensible threshold exists, evaluate:

* threshold-crossing detection;
* false alerts;
* missed events;
* precision;
* recall;
* F1 where appropriate;
* event lead time;
* time-to-threshold error;
* calibration of threshold-crossing probability.

The exact event definition remains dependent on the selected state and threshold.

---

# 24. Lead Time

Lead time is a key operational metric.

Conceptually:

$$
LeadTime =
t_{threshold} -
t_{alert}
$$

where:

* \(t_{threshold}\) = observed or defined threshold-crossing time;
* \(t_{alert}\) = time at which the system issued a qualifying warning.

A warning issued too late may have excellent classification accuracy but limited operational value.

A warning issued too early may have excessive false-alert burden.

Therefore lead time must be evaluated jointly with accuracy and false alerts.

---

# 25. False-Alert Burden

The system should not optimise simply for maximum alert sensitivity.

False alerts may cause:

* alert fatigue;
* unnecessary investigation;
* unnecessary operational action;
* loss of trust.

The evaluation should therefore consider:

* number of alerts;
* false-alert rate;
* alert duration;
* repeated alerts for the same event;
* lead time;
* missed events.

The acceptable burden is an open product decision.

---

# 26. Forecast Residuals

Residuals should be analysed for:

* bias;
* autocorrelation;
* changing variance;
* seasonal structure;
* systematic underprediction;
* systematic overprediction;
* behaviour during rainfall;
* behaviour during dry-down;
* behaviour near thresholds.

Residual autocorrelation is especially important because sequential forecast errors are not necessarily independent.

---

# 27. Prediction Intervals and Sequential Alerts

A sequence of observations outside a prediction interval must not automatically be interpreted using:

$$
P(\text{N consecutive breaches}) = \alpha^N
$$

because forecast residuals may be autocorrelated.

Therefore:

> **N-of-M alert rules are engineering persistence filters, not automatically valid statistical false-alarm probabilities.**

Any persistence rule must be evaluated empirically.

---

# 28. Candidate Forecasting Ladder

The initial modelling ladder is:

```text
LEVEL 0
Persistence

LEVEL 1
Seasonal / climatological baseline

LEVEL 2
Rolling / EWMA baseline

LEVEL 3
ETS / ARIMA / SARIMA

LEVEL 4
Dynamic regression / SARIMAX

LEVEL 5
Quantile regression / tree-based probabilistic models

LEVEL 6
More complex sequence models, only if justified
```

The project should stop climbing the ladder when additional complexity fails to produce material value.

---

# 29. Model Escalation Criteria

A more complex model may be promoted when it demonstrates consistent improvement in one or more meaningful dimensions:

* lower point forecast error;
* better skill relative to persistence;
* better threshold-event detection;
* useful additional lead time;
* improved uncertainty calibration;
* narrower intervals at comparable coverage;
* stability across seasons;
* stability across sites;
* improved residual structure.

A small improvement in one average metric is not automatically sufficient.

---

# 30. Model Rejection Criteria

A model should be rejected or deferred if:

* it does not consistently beat persistence;
* gains disappear under leakage-safe evaluation;
* gains occur only at one horizon;
* average error improves while threshold detection worsens;
* uncertainty is poorly calibrated;
* performance is unstable across time;
* performance depends on unavailable operational features;
* complexity materially increases maintenance without decision value;
* the dataset is too small to support reliable model selection.

---

# 31. Ablation Experiments

Feature groups should be evaluated using controlled comparisons where practical.

Examples:

### Baseline

Target history only.

### + Weather

Target history + precipitation + temperature + humidity.

### + Atmospheric Demand

Previous model + ET0/VPD.

### + Context

Previous model + soil/site/crop context.

The purpose is to determine whether additional variables provide measurable predictive value.

Feature importance alone is not sufficient evidence of operational usefulness.

---

# 32. Forecast Uncertainty by Horizon

Uncertainty is expected to increase as the forecast horizon extends, although the exact behaviour is data- and model-dependent.

Evaluation should therefore report uncertainty separately for each horizon.

For example:

| Horizon | Point Error | Coverage | Interval Width |
| ------- | ----------: | -------: | -------------: |
| Short   |         TBD |      TBD |            TBD |
| 24h     |         TBD |      TBD |            TBD |
| 72h     |         TBD |      TBD |            TBD |
| 168h    |         TBD |      TBD |            TBD |

No target performance values are assumed in advance.

---

# 33. Forecast Output Contract

A forecast record should conceptually contain:

```text
forecast_id
forecast_origin
target_timestamp
site_id
sensor_id / state_id
target_definition
horizon
point_forecast
lower_quantile / lower_bound
upper_quantile / upper_bound
model_version
training_data_reference
feature_set_reference
forecast_scenario
provenance
```

The exact machine-readable schema belongs in:

`07_contracts/EVENT_TELEMETRY_CONTRACT.md`

---

# 34. Reproducibility Requirements

Every forecasting experiment must record:

* dataset/source;
* dataset version or retrieval reference;
* retrieval date;
* time period;
* target definition;
* sensor depth;
* unit;
* preprocessing;
* missing-data policy;
* quality-control policy;
* feature definitions;
* forecast horizons;
* forecast scenario;
* train/validation/test periods;
* walk-forward methodology;
* model;
* hyperparameters;
* random seed where applicable;
* code version/commit;
* metrics;
* uncertainty metrics;
* event metrics;
* assumptions;
* limitations.

A forecast result without this metadata is not considered reproducible evidence.

---

# 35. Final Test Protection

The final test period must not influence:

* feature selection;
* model selection;
* hyperparameter tuning;
* threshold selection;
* horizon selection;
* alert-rule selection.

The final test exists to provide an independent estimate of performance after development decisions are complete.

---

# 36. Forecast Experiment Matrix

The initial experiment matrix should resemble:

| Experiment | Target         | Features                        | Model                  | Scenario | Status    |
| ---------- | -------------- | ------------------------------- | ---------------------- | -------- | --------- |
| F-001      | Selected state | Persistence only                | Persistence            | A        | REQUIRED  |
| F-002      | Selected state | Historical target               | Seasonal baseline      | A        | CANDIDATE |
| F-003      | Selected state | Historical target               | ETS/ARIMA              | A        | CANDIDATE |
| F-004      | Selected state | Target + observed covariates    | Dynamic regression     | B        | CANDIDATE |
| F-005      | Selected state | Target + operational covariates | Dynamic regression     | C        | CANDIDATE |
| F-006      | Selected state | Target + covariates             | Quantile model         | C        | CANDIDATE |
| F-007      | Selected state | Target + covariates             | Tree-based model       | C        | CANDIDATE |
| F-008      | Selected state | Selected feature set            | Complex sequence model | C        | DEFERRED  |

These experiments must be updated once the actual dataset and target are known.

---

# 37. Minimum Evidence for Forecast Validation

The forecasting component cannot be considered validated merely because:

* the model runs;
* a forecast graph looks plausible;
* training loss decreases;
* a test suite passes;
* a complex model produces predictions.

Validation requires evidence that:

1. the target is scientifically defined;
2. the forecast origin is explicit;
3. leakage has been controlled;
4. persistence has been evaluated;
5. chronological evaluation has been performed;
6. the final test was protected;
7. performance is reported by horizon;
8. uncertainty is evaluated if probabilistic forecasts are claimed;
9. threshold/event performance is evaluated where applicable;
10. results are reproducible.

---

# 38. Scientific and Operational Interpretation

Forecast performance must be interpreted separately from operational usefulness.

A model may have:

* lower MAE but no improvement in threshold-event detection;
* better average error but poor calibration;
* excellent short-horizon performance but insufficient 72-hour lead time;
* good statistical performance but require unavailable future inputs.

Therefore:

> **Forecast accuracy is necessary evidence, but not by itself evidence of operational value.**

---

# 39. Open Forecasting Decisions

The following remain intentionally unresolved:

1. Final forecast target.
2. Final target transformation.
3. Final sensor depth/state representation.
4. Final horizon set.
5. Forecast cadence.
6. Exogenous feature set.
7. ET0 implementation.
8. VPD implementation.
9. Treatment of future weather information.
10. Probabilistic forecasting method.
11. Event/threshold evaluation definition.
12. Acceptable forecast error.
13. Acceptable uncertainty miscalibration.
14. Acceptable false-alert burden.
15. Minimum useful lead time.
16. Whether multi-site validation is feasible.
17. Whether model complexity beyond statistical baselines is justified.

These decisions should be resolved through experiments rather than predetermined architecture.

---

# 40. Forecasting Status

| Area                       | Status      |
| -------------------------- | ----------- |
| Forecasting objective      | DECIDED     |
| Persistence baseline       | DECIDED     |
| Chronological evaluation   | DECIDED     |
| Walk-forward evaluation    | DECIDED     |
| Final target               | RESEARCHING |
| Forecast horizons          | RESEARCHING |
| Feature set                | RESEARCHING |
| Statistical model          | OPEN        |
| ML model                   | OPEN        |
| Probabilistic method       | RESEARCHING |
| Threshold-event evaluation | OPEN        |
| Alert persistence          | OPEN        |
| Multi-site validation      | OPEN        |
| Deep learning              | DEFERRED    |

---

# 41. Traceability

This document is governed by:

* `00_project/PROJECT_CHARTER.md`
* `01_research/RESEARCH_FEASIBILITY.md`
* `02_product/PRD.md`
* `03_scientific/DATA_SCIENTIFIC_SPEC.md`

It informs:

* `05_architecture/TECHNICAL_SPEC.md`
* `06_decisions/ADR_INDEX.md`
* `07_contracts/EVENT_TELEMETRY_CONTRACT.md`
* `08_implementation/IMPLEMENTATION_PLAN.md`
* `09_evidence/EXPERIMENT_LOG.md`

Forecasting decisions that materially affect system architecture must be reflected in an ADR.

---

# 42. Current Status

**Overall Status: RESEARCHING**

The project has a defined forecasting philosophy and evaluation framework.

The following are intentionally not yet frozen:

* exact target;
* final state representation;
* forecast horizons;
* feature set;
* probabilistic model;
* threshold-event definition;
* operational alert criteria.

The immediate priority is therefore empirical:

> **Select and audit the observational dataset, establish the forecasting target, construct leakage-safe evaluation periods, and measure persistence before escalating model complexity.**

---

# 43. Next Gate

### Forecastability Gate

Required evidence:

1. usable observational dataset;
2. defined target candidate;
3. temporal integrity audit;
4. missingness/QC assessment;
5. persistence benchmark;
6. baseline horizon evaluation;
7. initial uncertainty experiment;
8. evidence on whether additional features materially improve forecast skill.

Only after these results should the project decide whether more complex forecasting models are warranted.

```

### What I would **not** add yet

I would resist adding a giant model catalogue, detailed hyperparameter grids, LSTM architectures, Optuna, XGBoost settings, etc. That's exactly where this project could start becoming architecture theatre.

The important thing we've now locked is the **experimental logic**:

**Target → information available at t → horizon → persistence → simple baselines → probabilistic evaluation → threshold/event value → only then complexity.**

And importantly, this document doesn't contradict the previous Scientific Spec: **we still don't know whether the final target should be raw soil moisture, depletion, available-water fraction, or another state.**

So after this, the natural sequence remains:

**05 `TECHNICAL_SPEC.md` → 06 ADRs → 07 Event/Telemetry Contract → 08 Implementation Plan.**

But I would only start the Technical Spec after we have decided how much of the scientific uncertainty we actually need architecture to support.
```
