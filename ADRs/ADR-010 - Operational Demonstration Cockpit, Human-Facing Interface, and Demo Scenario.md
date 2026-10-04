# ADR-010: Operational Demonstration Cockpit, Human-Facing Interface, and Demo Scenario

## Status
**ACCEPTED** (Formally Adopted — Phase 6)

## Date
2026-10-04

## Context
Phases 1 through 5 established, evidenced, audited, and operationally packaged the scientific core of the Agri Telemetry & Forecasting Platform:
- In-situ soil moisture telemetry ingestion and Tier-1 quality control quarantine (`Tier1QCEngine`);
- Multi-layer root-zone soil water state construction (`StateBuilder`);
- Multi-horizon statistical and environmental forecasting (`PersistenceModel`, `EnvironmentalForecaster`, `ResilientForecastRouter`);
- Dynamic regime-conditioned uncertainty calibration (`RegimeConditionedCalibrator`);
- Multi-horizon MAD/wilting risk evaluation and stateful advisory persistence filtering (`OperationalAdvisoryEngine`);
- Multi-site cross-climate validation across 6 independent USCRN stations (`MultiSiteEvaluator`);
- Resilient edge IoT MQTT stream ingestion with deduplication and Dead Letter Queue (`MQTTTelemetryIngestAdapter`).

While the underlying engine was verified through 68+ unit and integration tests and MLOps evidence tracking, human operators, agronomists, and evaluators required an intuitive, transparent, and verifiable human-facing interface to inspect real-time state, visualize multi-horizon forecasts with calibrated uncertainty envelopes, observe live quality control quarantines, and execute reproducible demonstration scenarios.

Phase 6 provides the human-facing operational cockpit and demonstration harness for the platform.

---

## Decision Drivers
1. **Zero-Dependency Simplicity:** The presentation layer must run anywhere without node, npm, webpack, or external web frameworks. It must use Python standard library (`http.server`) and vanilla HTML5/CSS3/Canvas.
2. **Scientific Honesty & Horizon Distinction:** Visualizations must strictly reflect empirical findings: 1–48h prediction intervals are labeled `80% Prediction Interval (Partially Supported)`, while 72–168h intervals are labeled `Empirical Uncertainty Interval (Research)` and rendered with visually distinct styling.
3. **Dynamic Threshold Integrity:** Soil thresholds ($\theta_{\text{fc}}, \theta_{\text{wp}}, \theta_{\text{mad}}$) must be computed dynamically from the active station profile metadata ($\theta_{\text{mad}} = \theta_{\text{fc}} - D_{\text{mad}} \times (\theta_{\text{fc}} - \theta_{\text{wp}})$), never hard-coded.
4. **Data Quality Fault Isolation:** The interface and demo harness must explicitly verify that quarantined telemetry anomalies emit data-quality warnings while completely preventing false agronomic advisories (*"No agronomic advisory generated from the quarantined synthetic spike"*).
5. **Clear Provenance & Non-Actuation:** The interface must prominently display data provenance (`SIMULATED_REPLAY` vs `OBSERVED_IN_SITU`) and maintain strict non-actuating decision support guarantees (`is_autonomous_actuation: False`).

---

## Decisions

### 1. Presentation Architecture & Zero-Dependency HTTP Server
We implemented `agri_telemetry.ui.server`:
- `DashboardSession`: Thread-safe operational state manager hosting the live streaming broker, MQTT adapter, QC engine, state builder, multi-horizon forecasters, and advisory engine in-memory.
- `DashboardServer`: Zero-dependency HTTP server subclassing `http.server.ThreadingHTTPServer` and `SimpleHTTPRequestHandler`.
- **JSON API Endpoints:**
  - `GET /api/status`: Returns current soil state, 168h forecast with quantile envelopes, active advisories, QC health, stream counters, and event logs.
  - `GET /api/sites`: Returns station catalog (simulated edge node and physical USCRN stations).
  - `POST /api/select-site`: Dynamically reconfigures station metadata, soil hydraulic limits, and state history.
  - `POST /api/step`: Advances live stream by $N$ hours.
  - `POST /api/inject-fault`: Injects unphysical spikes, stuck sensors, packet drops, or duplicate frames.
  - `POST /api/reset`: Resets session to initial baseline state.

### 2. Simplified Operational Cockpit Layout
We created a clean, distraction-free web dashboard (`agri_telemetry/ui/static/`):
- **Top Bar:** Station name, data provenance tag (`SIMULATED_REPLAY` / `OBSERVED_IN_SITU`), simulation badge, and current timestamp.
- **Primary Telemetry & State Panel:** Large volumetric water content ($\theta_{\text{rz}}$), depletion fraction ($D_r$), root-zone storage, deficit mm, and QC health indicator.
- **Main Trajectory Chart:** Canvas-based interactive multi-horizon visualizer displaying:
  - 48-hour observed telemetry history (solid line).
  - 168-hour forecast trajectory (dashed line).
  - Dual-shaded uncertainty ribbons:
    - 1–48h: Light teal shaded ribbon labeled `80% Prediction Interval (Partially Supported)`.
    - 72–168h: Dashed border ribbon labeled `Empirical Uncertainty Interval (Research)`.
  - Dynamic agronomic reference lines: Field Capacity ($\theta_{\text{fc}}$), Management Allowed Depletion ($\theta_{\text{mad}}$), and Permanent Wilting Point ($\theta_{\text{wp}}$).
- **Advisory & Guidance Card:** Active advisory severity (`NORMAL`, `WARNING`, `CRITICAL`), category (`AGRONOMIC_WATER_RISK`, `DATA_QUALITY_ALERT`), human-in-the-loop action text, and non-actuation guarantee banner.
- **Collapsible Control Drawer:** Step controls (+1h, +6h, +24h), fault injection triggers, station switcher, and real-time structured audit log.

### 3. Automated Demonstration Scenario Runner (`agri_telemetry.simulation.demo_runner`)
We created `Phase6DemoRunner` executing a standardized 5-step operational demonstration:
1. **Step 1 (Baseline Ingestion):** Ingests healthy simulated ESP32 MQTT packet, constructs root-zone state, emits 7-horizon forecast, and confirms `NORMAL` advisory status.
2. **Step 2 (Sensor Spike Quarantine):** Injects unphysical $0.88\text{ m}^3/\text{m}^3$ sensor spike; verifies Tier-1 QC quarantine, emits `DATA_QUALITY_ALERT`, and confirms that **no agronomic advisory is generated from the quarantined synthetic spike**.
3. **Step 3 (Duplicate Packet Suppression):** Injects duplicate packet; verifies idempotent SHA-256 deduplication and increments dropped counter with zero pipeline state mutation.
4. **Step 4 (Soil Drydown & MAD Evaluation):** Advances telemetry through 12 hours of dry daylight evapotranspiration; verifies cumulative deficit tracking and forecast trajectory update.
5. **Step 5 (Multi-Site Station Switching):** Switches active station to physical USCRN station (`IL_Champaign_9_SW`); verifies dynamic reloading of soil parameters ($\theta_{\text{fc}}=0.34, \theta_{\text{wp}}=0.14, \theta_{\text{mad}}=0.24$) and in-situ observed provenance.

The demonstration exports structured evidence to `runs/phase6_demo_summary.json` (`EVD-030`).

### 4. CLI Integration
Added CLI subcommands in `agri_telemetry.cli`:
- `agri-telemetry dashboard [--host HOST] [--port PORT]`: Launches local HTTP server and prints cockpit URL.
- `agri-telemetry demo [--save-report]`: Runs headless 5-step demonstration and outputs structured findings.

---

## Consequences

### Positive Consequences
- **Zero Installation Overhead:** Operators can run the cockpit immediately on any workstation with standard Python 3.11+.
- **End-to-End Verification:** Demonstrates complete vertical slice from edge MQTT ingestion through QC quarantine, state builder, hybrid forecasting, and advisory generation.
- **Scientific Integrity:** Strictly prevents over-claiming by separating partially supported short-horizon uncertainty from research long-horizon uncertainty on charts and API responses.
- **Auditable Fault Isolation:** Proves in real-time that corrupted telemetry cannot trigger erroneous irrigation advisories.

### Limitations & Negative Consequences
- **Operational Boundary:** Phase 6 is operationally packaged and locally verified; production deployment and field-scale operational validation remain outside the current evidence base.
- **Local Browser Rendering:** Pure Canvas drawing requires no external charting library (e.g. Chart.js / D3), keeping dependencies zero, but features like rich chart tooltips are intentionally minimal.
- **Demonstration Scope:** Demonstration soil thresholds ($D_{\text{mad}}=0.50$) illustrate decision-support mechanics and do not constitute universal agronomic crop truth.
