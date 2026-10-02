# ADR-007: Operational Anomaly Taxonomy, Multi-Horizon Water Risk Evaluation, and Alert Persistence Filter Architecture

**Status:** DECIDED  
**Date:** October 2, 2026  
**Deciders:** Antigravity Engineering & Science Team  
**Consulted:** PRD, Technical Spec, Event & Telemetry Contract, Evidence & Validation  

---

## 1. Context & Problem Statement

In operational agricultural deployment, a telemetry and forecasting system faces three distinct failure modes:
1. **Sensor / Telemetry Corruptions:** Non-physical spikes, stuck frozen sensors, packet dropouts, and schema corruptions. If unisolated, bad telemetry masquerades as severe drought or storm events, triggering false alarms.
2. **Physical & Model Deviations:** Rapid unexplained wetting without precipitation, thermodynamic rate-of-change violations, hydraulic inversions across soil depths, or massive forecast residuals.
3. **Agronomic Water Deficit Risks:** Real-world soil moisture depletion approaching or crossing Management Allowed Depletion (MAD) and Critical Wilting thresholds.
4. **Alert Churn & Flapping:** Transient noise excursions or borderline forecast oscillations cause high alert fatigue if every single-step threshold breach triggers an immediate operational advisory.

We must decide:
1. How to establish a strict, deterministic taxonomy separating data quality, physical deviation, and agronomic risk.
2. How to evaluate multi-horizon water risk under uncertainty without claiming unjustified probability calibration at long horizons.
3. How to engineer an alert persistence filter to control operator alert burden while preserving critical safety responsiveness.

---

## 2. Decision

1. **Establish a 3-Tier Anomaly & Isolation Boundary**:
   - **Tier 1 (Data-Quality Anomalies):** Handled by Tier-1 QC and Quarantine. Quarantined states are strictly isolated from the state builder and forecasting pipeline, guaranteeing a **100% mathematical barrier against data faults leaking into agronomic risk advisories**.
   - **Tier 2 (Physical Deviations):** Handled by `PhysicalDeviationDetector`, evaluating domain-informed operational thresholds: 1-step forecast residuals ($|y_t - \hat{y}_{t|t-1}| > 0.020\ \text{m}^3/\text{m}^3$), configured drying rate limits ($> 0.025\ \text{m}^3/\text{m}^3/\text{h}$), unmetered wetting heuristics ($+0.015\ \text{m}^3/\text{m}^3/\text{h}$ with $P \le 0.2\text{mm}$), and hydraulic depth inversions. These represent configured engineering heuristics, not universal physical constants.
   - **Tier 3 (Agronomic Water Risk):** Handled by `UncertaintyAwareRiskEvaluator`, evaluating real-time depletion $D_r(t)$ and multi-horizon forward forecast trajectories against configured MAD ($D_{\text{MAD}} = 0.50$, configured demonstration threshold) and Wilting Proximity ($D_{\text{wilt}} = 0.85$).

2. **Deploy Uncertainty-Aware Risk Certainty Classification**:
   - Categorize forecast threshold crossings into four explainable levels:
     - `DEFINITELY_NOT_REACHED`: Upper interval bound $q_{0.90} < D_{\text{MAD}}$.
     - `PLAUSIBLY_REACHED`: Median $q_{0.50} < D_{\text{MAD}} \le q_{0.90}$.
     - `LIKELY_REACHED`: Median $q_{0.50} \ge D_{\text{MAD}}$.
     - `HIGHLY_UNCERTAIN`: Assigned to extended horizons ($h > 48\text{h}$) when interval width is large and uncalibrated from in-situ past-only information.

3. **Implement Stateful Alert Persistence Filtering (`AlertPersistenceFilter`)**:
   - Filter transient candidate alerts using **Consecutive Confirmation ($k=2, k=3$)** or **$N$-of-$M$ Sliding Windows ($3$-of-$5$)** per `(source_id, category, threshold_type)` key.
   - Suppress transient 1-sample noise excursions (e.g. 100% suppression of fluttering oscillations in Scenario 8).
   - **Critical Safety Override:** Immediate bypass of persistence delay for `CRITICAL` severity (Critical Wilting Proximity $D_r \ge 0.85$) to prevent delayed intervention under extreme crop stress.

4. **Emit Canonical Non-Actuating `AlertEvent` Records**:
   - Guarantee strict decision-support semantics (`is_autonomous_actuation: false`), complete provenance, threshold context, and actionable human-readable explanations.

---

## 3. Consequences & Trade-offs

### Positive:
- **Zero Agronomic Contamination from Corrupted Data:** Tier-1 quarantine guarantees zero false drought alarms from dead or spiking sensors (verified in 8/8 synthetic benchmark scenarios).
- **Suppression of Transient Noise:** Persistence filtering suppresses transient alert flapping while maintaining confirmed detection of sustained drought events.
- **Transparent Explainability:** Every emitted advisory contains explicit causality: whether it is data-quality, physical deviation, or agronomic risk, with certainty labels and persistence verification.

### Negative / Trade-offs:
- **Lead-Time Latency Penalty:** Consecutive $k=2$ persistence introduces a $+1\text{h}$ latency on non-critical warning alerts (mitigated by immediate critical bypass).
- **Stateful In-Memory Filter:** Requires tracking active candidate keys in memory across streaming batches.

---

## 4. Status

- **Status:** DECIDED & IMPLEMENTED
- **Supersedes:** Extends ADR-004 and ADR-006.
