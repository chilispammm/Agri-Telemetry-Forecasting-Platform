# ADR-009: Multi-Site Generalisation, External Validation, and MQTT Telemetry Integration

## Status
**ACCEPTED** (Formally Adopted — Phase 5)

## Date
2026-10-02

## Context
Phases 1 through 4 developed, strengthened, audited, and operationally packaged the Agri Telemetry & Forecasting Platform using in-situ observations from a single canonical reference station: **USCRN Lincoln 11 SW, Nebraska (2023)**. While the platform achieved rigorous reproducibility, leak-free walk-forward validation, positive forecasting skill, noise-suppressed advisory episode generation, and resilient streaming architecture, the core scientific and operational conclusions remained verified only within that single geographic and pedological setting.

Phase 5 addresses the critical external validation question:
> *Does the forecasting, uncertainty, anomaly, and advisory framework generalise across independent sites and realistic telemetry delivery conditions, and where does its performance or calibration break down?*

In accordance with project governance, Phase 5:
1. Audits independent external USCRN stations across distinct CONUS climate regimes.
2. Evaluates out-of-site forecasting transfer (B0 vs M1 vs M2 vs Hybrid).
3. Evaluates uncertainty transfer (Static U0 vs Dynamic U2).
4. Evaluates advisory generation, flutter suppression, and episode grouping.
5. Implements edge microcontroller telemetry ingestion via MQTT (simulating ESP32/Wokwi hardware) with strict simulation provenance tagging.
6. Evaluates system robustness under stochastic packet loss, out-of-order network jitter, and seasonal transitions (winter freeze vs summer convective drydown).

---

## Decision Drivers
1. **Empirical Boundary Discovery:** Identify where in-situ statistical/environmental models succeed, degrade, or fail catastrophically across varied climate regimes and soil hydraulic textures.
2. **Uncertainty Truth in Advertising:** Preserve strict calibration claims—short-horizon (1–48h) dynamic uncertainty is partially supported; >48h calibration remains an open research question across all evaluated sites.
3. **Agronomic Boundary Discipline:** Distinguish mathematical transfer, implementation transfer, and empirical generalisation from universal agronomic validity. Never claim demonstration thresholds constitute universal crop-response truth.
4. **Simulation Provenance Transparency:** Ensure telemetry generated from edge simulators (ESP32 / Wokwi) is explicitly tagged as simulated (`DataClass.SIMULATED_REPLAY`, `network: "ESP32_MQTT_SIMULATED"`), preventing any confusion with physical ground truth.
5. **Transport Resilience:** Ensure IoT edge ingest gracefully handles broken payloads, network duplicates, out-of-order packets, and connection dropouts without crashing the operational stream.

---

## Decisions

### 1. Multi-Site Benchmark Catalog & Selection Methodology
We established a typed station registry (`agri_telemetry.data.site_registry`) auditing candidate stations across CONUS climate regimes:
- **Baseline Reference:** `NE_Lincoln_11_SW` (Humid Continental Plains / Western Corn Belt, Silt Loam, 611.5 mm annual precip).
- **Core Agricultural Evaluation Sites:**
  - `IL_Champaign_9_SW` (Midwest Corn Belt, Silt Loam / Drummer Clay, 832.0 mm precip, 99.1% probe completeness).
  - `SD_Sioux_Falls_14_NNE` (Northern Great Plains, Silty Clay Loam, 599.2 mm precip, 99.9% probe completeness).
- **Arid Benchmark Site:** `NM_Las_Cruces_20_N` (Desert Southwest / Jornada Basin, Sandy Loam, 169.8 mm precip, 99.6% probe completeness).
- **Humid Subtropical Benchmark Site:** `GA_Watkinsville_5_SSE` (Southeastern Ultisol, Cecil Sandy Clay Loam, 1339.0 mm precip, 93.0% probe completeness).
- **Semi-Arid Benchmark Site:** `CO_Nunn_7_NNE` (High Plains Shortgrass Steppe, Ascalon Loam, 344.8 mm precip, 89.8% probe completeness).
- **Formal Station Exclusion Catalog:**
  - `TX_Austin_33_NW`: Excluded due to uninstalled 20cm, 50cm, and 100cm probes preventing root-zone profile integration.
  - `AL_Selma_13_WNW`: Excluded due to >50% missingness at depth probes.
  - `IA_Des_Moines_17_E`: Excluded due to 35.5% growing season sensor missingness breaking chronological continuity.

### 2. Multi-Site Forecasting & Uncertainty Transfer Architecture
We implemented `MultiSiteEvaluator` executing strict 50/50 chronological split evaluations per station:
- **Forecast Model Generalisation Findings:**
  - *Midwest & Continental Steppe (`IL_Champaign_9_SW`, `SD_Sioux_Falls_14_NNE`, `NE_Lincoln_11_SW`):* M2 Environmental forecaster achieves consistent positive skill (+11.15% in Champaign, +7.36% in Sioux Falls, +3.57% in Lincoln) over 1–48h by capturing diurnal solar radiation and drying dynamics.
  - *Arid Regime (`NM_Las_Cruces_20_N`):* M2 achieves +11.96% MSE skill (+35.4% at 6h) due to extreme diurnal solar forcing in sandy soils.
  - *Subtropical Failure Boundary (`GA_Watkinsville_5_SSE`):* M2 exhibits negative skill (-18.96% overall, -45.1% at 24h) and degrades relative to persistence. Intense, unpredicted convective summer storms (50mm+ pulses) arrive without antecedent signal in past in-situ telemetry, causing massive forecast error spikes.
- **Uncertainty Calibration Transfer:**
  - Short-horizon (1–48h) U2 dynamic condition-scaling partially transfers across temperate and arid sites, improving active infiltration coverage, but under-covers in tropical/subtropical high-intensity storm regimes.
  - Long-horizon (>48h) calibration remains uncalibrated research across all sites (coverage drops to 50–65% at 168h without forward NWP).

### 3. Advisory & Risk Episode Transfer
We evaluated `OperationalAdvisoryEngine` across all sites:
- **Flutter Suppression:** The stateful persistence filter ($k=2, k=3, 3\text{-of-}5$) completely suppresses 100% of single-hour transient noise and threshold boundary jitter across all soil regimes.
- **Episode Compression:** $G=6\text{h}$ episode grouping compresses raw alerts into actionable continuous risk episodes with >95% volume compression across all stations (36 episodes in Lincoln, 48 in Champaign, 2 in Las Cruces, 58 in Watkinsville, 1 in Nunn, 93 in Sioux Falls).

### 4. Edge IoT MQTT Telemetry Ingress Adapter (`agri_telemetry.streaming.mqtt_adapter`)
We introduced an MQTT 5 telemetry ingress adapter bridging field edge microcontrollers into the streaming platform:
- **Simulation Transparency:** Telemetry from `ESP32TelemetrySimulator` is strictly stamped with `DataClass.SIMULATED_REPLAY` and provenance network `ESP32_MQTT_SIMULATED`.
- **Fault-Tolerant Ingestion Pipeline:**
  1. *Schema Decoding & DLQ:* Malformed JSON payloads or non-compliant structures are routed directly to `DeadLetterQueue` with error diagnostics.
  2. *Idempotent Deduplication:* `EventDeduplicator` computes SHA-256 keys across `(source_id, site_id, timestamp)` to drop duplicate cellular retransmissions.
  3. *Out-of-Order Resequencing:* `OutOfOrderSequencer` buffers windowed events to restore chronological sequence before stream publication.

### 5. Failure Boundary & Stress-Testing Findings (`agri_telemetry.experiments.robustness_analysis`)
- **Packet Loss Limit:** State reconstruction MAE stays $<0.0005\,\text{m}^3/\text{m}^3$ up to 20% random packet drop; begins degrading substantially at $\ge 35\%$ loss due to missed sharp infiltration events.
- **Jitter Resilience:** `OutOfOrderSequencer` achieves 100.0% chronological order restoration under 25% delayed packet arrival injection.
- **Frozen Ground Dielectric Boundary:** During winter sub-zero temperatures (Jan–Feb), dielectric permittivity flatlines as soil water freezes into ice. Empirical uncertainty intervals under-cover (68% vs nominal 80%), indicating physical freeze flags must suspend hydraulic depletion models.

---

## Consequences & Governance Protections

### Positive Consequences
- Proven transferability of the core hybrid forecasting and advisory architecture to independent agricultural sites in the Midwest Corn Belt and Northern Plains.
- Explicit empirical discovery of the subtropical convective storm failure boundary, proving why future NWP/radar integration is indispensable for long horizons.
- Production of a robust, decoupled edge IoT MQTT adapter with built-in dead letter queuing, deduplication, and packet resequencing.

### Boundaries & Negative Consequences
- **Local Empirical Uncertainty Limit:** In-situ telemetry alone cannot maintain reliable prediction interval coverage beyond 48h during active convective seasons.
- **Demonstration Agronomic Status:** Soil hydraulic thresholds ($d_{mad}=0.50$, $d_{wilt}=0.85$) demonstrate software decision filtering mechanics only; crop-specific field tuning remains mandatory before any physical deployment.

---

## Status and Verification
- Multi-site benchmark report generated: `runs/multisite_validation_report.json`
- Robustness report generated: `runs/robustness_report.json`
- Test suite: 68 authoritative tests passing (100% pass rate).
- Phase status: **PHASE 5 COMPLETED AND FROZEN**.
