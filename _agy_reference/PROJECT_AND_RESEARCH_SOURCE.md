Here are the formal `PROJECT_CHARTER.md` and `PROJECT_CHARTER.html` documents, strictly incorporating your rules, the exact formatting from `image_037a51.png`, and the empirical research from Perplexity.

### 1. `00_project/PROJECT_CHARTER.md`

Markdown

```
# Agri Telemetry & Forecasting Platform — Project Charter

**Status:** RESEARCHING  
**Last Updated:** September 28, 2026

## Document Authority
This charter defines project intent, boundaries, and evaluation criteria. Later specifications (e.g., Data/Scientific Spec, PRD) and Architecture Decision Records (ADRs) will define detailed mathematical, scientific, and technical decisions based on empirical evidence.

---

## 01. Project Brief

**Central Operational Question**  
"Given measured root-zone water status, crop stage, soil properties, irrigation/rainfall inputs, and near-term atmospheric demand, will the field reach a management threshold before the next feasible irrigation opportunity—and with what confidence?"

**Working Hypothesis**  
Continuous telemetry can establish a conditional temporal baseline for a field's water balance. Deviations from this baseline, when combined with near-term weather forecasts, provide actionable lead time to prevent crop-stress threshold breaches.

**Product Concept & Primary Objective**  
An operational time-series intelligence system that reconstructs field water-status from incoming telemetry, forecasts near-term depletion trajectories with uncertainty, and identifies potential threshold risks early enough to support an irrigation decision.

**Target User / Decision-Maker**  
[ UNKNOWN ] (To be defined in PRD. Examples may include farm operators or agronomists).

**Portfolio Differentiation (Capabilities Demonstrated)**  
* *Crop Stress Intelligence* = Remote Sensing / Geospatial screening (**Spatial** context).
* *This Project* = Event-Driven MLOps / IoT Simulation / Time-Series (**Temporal** context).

**Explicit Non-Goals / Out-of-Scope**  
* Physical hardware deployment.
* Integration with proprietary farm APIs.
* Full-scale UI dashboards (until the API is fully proven).
* Automatic site-crop monitoring and multi-spectral analysis.
* Universal numeric thresholds for Management Allowable Depletion (MAD).

---

## 02. Research-Derived Constraints & Terminology

* **MAD (Management Allowable Depletion):** Must be a configurable agronomic threshold, not a universal hardcoded numeric value.
* **Forecast Horizons:** Forecasts are valuable within a 1-to-7-day decision window. Horizons beyond 14 days are exploratory.
* **Telemetry Cadence:** Hourly observation is a defensible standard for simulating real field operations.
* **Event Taxonomy:** The system must differentiate between:
  * *Data-Quality Anomaly:* Sensor malfunction, drift, or communication error.
  * *Physical Deviation:* Unexpected drying/wetting (e.g., failed irrigation delivery, unrecorded rainfall).
  * *Agronomic Risk:* Trajectory indicating an impending MAD breach.

---

## 03. Scientific & Engineering Scope

| Variable / Input | Role | Source | Status |
| :--- | :--- | :--- | :--- |
| **Volumetric Soil Moisture** | Primary Target (at active root depth) | NOAA USCRN (In-Situ Candidate) | [ RESEARCHING ] |
| **Temperature & RH** | Explanatory Covariates | NOAA USCRN (In-Situ Candidate) | [ RESEARCHING ] |
| **Precipitation / Irrigation** | Direct Water Flux Inputs | NOAA USCRN (In-Situ Candidate) | [ RESEARCHING ] |
| **ET₀ / VPD** | Derived Atmospheric Demand | Calculated / Open-Meteo | [ ASSUMPTION ] |

| Engineering Component | Capability Required | Candidate Technology | Status |
| :--- | :--- | :--- | :--- |
| **Edge Simulation** | Generate structured JSON payloads with noise/drops | ESP32 Simulator / Wokwi | [ RESEARCHING ] |
| **Message Broker** | At-least-once telemetry delivery & buffering | Redis Streams / Kafka | [ OPEN ] |
| **Ingestion Protocol** | Edge-to-broker transport | MQTT 5 / HTTP | [ OPEN ] |
| **Forecasting Model** | Probabilistic depletion trajectory prediction | Persistence / SARIMAX / QRF | [ RESEARCHING ] |
| **MLOps Tracking** | Experiment, parameter, and metric lineage | MLflow Tracking | [ ASSUMPTION ] |

*Note: Deep Learning/LSTM is explicitly deferred until statistical baselines prove insufficient.*

---

## 04. Decision Gates & Validation Status

| Gate | Requirement | Status |
| :--- | :--- | :--- |
| **1. Problem Validated** | Is this a meaningful operational problem? | [ STRONGLY SUPPORTED ] |
| **2. Data Validated** | Can we obtain real historical telemetry for simulation? | [ RESEARCHING ] |
| **3. Forecasting Validated** | Is there a defensible prediction problem where persistence can be challenged? | [ RESEARCHING ] |
| **4. Architecture Validated** | Do the proposed technologies solve actual workload requirements? | [ OPEN ] |
| **5. End-to-End Validated** | Does the system process telemetry, emit forecasts, and generate accurate alerts? | [ NOT STARTED ] |

* **Current Project Status:** Research feasibility complete. Transitioning to Data Validation (Gate 2).
* **Next Decision Gate:** Execute NOAA USCRN station audit and EDA to validate Gate 2.

---

## 05. Risks & Open Questions

**Known Assumptions**
* Reliable telemetry reaches the system at a cadence appropriate to the decision.
* Soil-moisture sensors are installed in representative management zones at relevant depths.
* Crop identity, growth stage, soil characteristics, and basic weather data are known.

**Major Risks**
* *False Alarms via Autocorrelation:* A pointwise prediction interval breach does not provide a sequence-wise false-alarm guarantee due to serial correlation.
* *Reanalysis Substitution Error:* Using modelled/reanalysis soil moisture (ERA5-Land) as an exact "ground truth" target prevents the realistic simulation of physical sensor anomalies.
* *Data Leakage:* Randomly distributing timestamps from a weather event across train/test sets leaks future information. 

**Open Questions**
* What is the actual decision cadence for the end user (e.g., same-day intervention, 3-day scheduling)?
* How much forecast uncertainty can users accept before an alert becomes untrustworthy?
* Does the architecture genuinely require the independent consumer replay capabilities of Kafka, or is Redis Streams sufficient?

---
*Evidence Provenance: FAO-56 irrigation guidelines, USDA NRCS standards (CPS 449), UMN/Arizona Extension protocols, Copernicus C3S metadata, and ASCE/MDPI peer-reviewed literature.*

```

### 2. `00_project/PROJECT_CHARTER.html`

HTML

```
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agri Telemetry & Forecasting - Project Charter</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            color: #111;
            background-color: #fff;
            line-height: 1.6;
        }

        /* Sidebar Styling */
        .sidebar {
            width: 260px;
            height: 100vh;
            position: fixed;
            border-right: 3px solid #111;
            padding: 2rem 1.5rem;
            box-sizing: border-box;
            background-color: #fff;
            overflow-y: auto;
        }

        .sidebar-brand {
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #111;
            padding-bottom: 1rem;
            margin-bottom: 2rem;
        }

        .nav-item {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            color: #444;
            margin-bottom: 1.5rem;
            letter-spacing: 0.5px;
            cursor: pointer;
        }

        .nav-item:hover {
            color: #000;
        }

        /* Main Content Styling */
        .main-content {
            margin-left: 260px;
            padding: 3rem 4rem;
            max-width: 1000px;
            width: 100%;
            box-sizing: border-box;
        }

        .document-meta {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4rem;
        }

        .section-header {
            display: flex;
            align-items: baseline;
            border-bottom: 2px solid #111;
            padding-bottom: 0.5rem;
            margin-top: 4rem;
            margin-bottom: 2rem;
        }

        .section-number {
            font-size: 1.25rem;
            font-weight: 400;
            color: #666;
            margin-right: 1rem;
            font-family: monospace;
        }

        .section-title {
            font-size: 1.5rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: -0.5px;
        }

        .intro-text {
            font-size: 14px;
            color: #333;
            margin-bottom: 2rem;
        }

        /* Table Styling */
        table {
            width: 100%;
            border-collapse: collapse;
            border: 1px solid #111;
            margin-bottom: 3rem;
            font-size: 13px;
        }

        th, td {
            border: 1px solid #111;
            padding: 1.25rem;
            vertical-align: top;
        }

        th {
            text-transform: uppercase;
            font-weight: 700;
            background-color: #f9f9f9;
            text-align: left;
        }

        td.key-column {
            font-weight: 700;
            text-transform: uppercase;
            width: 25%;
            background-color: #fcfcfc;
        }

        /* Badge Styling */
        .badge {
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 3px 6px;
            border: 1px solid #111;
            display: inline-block;
            margin-right: 8px;
            letter-spacing: 0.5px;
        }

        .badge.assumption { color: #d97706; border-color: #d97706; }
        .badge.decided { color: #7c3aed; border-color: #7c3aed; }
        .badge.unknown { color: #4b5563; border-style: dashed; }
        .badge.validated { color: #059669; border-color: #059669; }
        .badge.researching { color: #2563eb; border-color: #2563eb; }
        .badge.open { color: #0ea5e9; border-color: #0ea5e9; }
        .badge.supported { color: #059669; border-color: #059669; border-style: dotted; }
        .badge.not-started { color: #6b7280; border-color: #6b7280; background-color: #f3f4f6; }

    </style>
</head>
<body>

    <!-- Sidebar -->
    <div class="sidebar">
        <div class="sidebar-brand">CA-ENG // MASTER RECORD</div>
        <div class="nav-item">Document Authority</div>
        <div class="nav-item">1. Project Brief</div>
        <div class="nav-item">2. Terminology</div>
        <div class="nav-item">3. Scientific Scope</div>
        <div class="nav-item">4. Decision Gates</div>
        <div class="nav-item">5. Risks & Open Questions</div>
    </div>

    <!-- Main Content -->
    <div class="main-content">
        
        <div class="document-meta">
            Agri Telemetry & Forecasting Platform<br>
            Status: <span class="badge researching" style="margin-left: 5px;">Researching</span><br>
            Last Updated: September 28, 2026
        </div>

        <div class="intro-text" style="font-style: italic; background-color: #f9f9f9; padding: 1rem; border-left: 3px solid #111;">
            <strong>Document Authority:</strong> This charter defines project intent, boundaries, and evaluation criteria. Later specifications (e.g., Data/Scientific Spec, PRD) and Architecture Decision Records (ADRs) will define detailed mathematical, scientific, and technical decisions based on empirical evidence.
        </div>

        <div class="section-header">
            <span class="section-number">01</span>
            <span class="section-title">Project Brief</span>
        </div>
        
        <table>
            <tr>
                <td class="key-column">Central Question</td>
                <td>"Given measured root-zone water status, crop stage, soil properties, irrigation/rainfall inputs, and near-term atmospheric demand, will the field reach a management threshold before the next feasible irrigation opportunity—and with what confidence?"</td>
            </tr>
            <tr>
                <td class="key-column">Working Hypothesis</td>
                <td>Continuous telemetry can establish a conditional temporal baseline for a field's water balance. Deviations from this baseline, when combined with near-term weather forecasts, provide actionable lead time to prevent crop-stress threshold breaches.</td>
            </tr>
            <tr>
                <td class="key-column">Target User</td>
                <td><span class="badge unknown">Unknown</span> (To be defined in PRD. Examples may include farm operators or agronomists).</td>
            </tr>
            <tr>
                <td class="key-column">Primary Objective</td>
                <td>An operational time-series intelligence system that reconstructs field water-status from incoming telemetry, forecasts near-term depletion trajectories with uncertainty, and identifies potential threshold risks early enough to support an irrigation decision.</td>
            </tr>
            <tr>
                <td class="key-column">Portfolio Differentiation</td>
                <td>
                    Crop Stress Intelligence = Remote Sensing / Geospatial screening (<strong>Spatial</strong> context).<br>
                    This Project = Event-Driven MLOps / IoT Simulation / Time-Series (<strong>Temporal</strong> context).
                </td>
            </tr>
            <tr>
                <td class="key-column">Explicit Non-Goals</td>
                <td>Physical hardware deployment, proprietary farm API integration, universal numeric MAD thresholds, or full-scale SaaS UIs.</td>
            </tr>
        </table>

        <div class="section-header">
            <span class="section-number">02</span>
            <span class="section-title">Research-Derived Constraints & Terminology</span>
        </div>

        <p class="intro-text">
            <strong>MAD (Management Allowable Depletion):</strong> Must be a configurable agronomic threshold, not a universal hardcoded numeric value.<br><br>
            <strong>Forecast Horizons:</strong> Forecasts are valuable within a 1-to-7-day decision window.<br><br>
            <strong>Event Taxonomy:</strong> The system must distinguish between: Data-Quality Anomalies (sensor drift), Physical Deviations (unrecorded rain), and Agronomic Risks (impending MAD breach).
        </p>

        <div class="section-header">
            <span class="section-number">03</span>
            <span class="section-title">Scientific & Engineering Scope</span>
        </div>

        <table>
            <tr>
                <th>Variable / Component</th>
                <th>Role</th>
                <th>Candidate / Source</th>
                <th>Status</th>
            </tr>
            <tr>
                <td style="font-weight: 600;">Volumetric Soil Moisture</td>
                <td>Primary Target (at depth)</td>
                <td>NOAA USCRN (In-Situ)</td>
                <td><span class="badge researching">Researching</span></td>
            </tr>
            <tr>
                <td style="font-weight: 600;">Precipitation / Temp</td>
                <td>Flux / Covariates</td>
                <td>NOAA USCRN (In-Situ)</td>
                <td><span class="badge researching">Researching</span></td>
            </tr>
             <tr>
                <td style="font-weight: 600;">ET₀ / VPD</td>
                <td>Atmospheric Demand</td>
                <td>Calculated / Open-Meteo</td>
                <td><span class="badge assumption">Assumption</span></td>
            </tr>
            <tr>
                <td style="font-weight: 600;">Message Broker</td>
                <td>At-least-once buffering</td>
                <td>Redis Streams / Kafka</td>
                <td><span class="badge open">Open</span></td>
            </tr>
            <tr>
                <td style="font-weight: 600;">Forecasting Model</td>
                <td>Depletion trajectory</td>
                <td>Persistence / SARIMAX / QRF</td>
                <td><span class="badge researching">Researching</span></td>
            </tr>
        </table>

        <div class="section-header">
            <span class="section-number">04</span>
            <span class="section-title">Decision Gates & Status</span>
        </div>

        <table>
            <tr>
                <th>Gate</th>
                <th>Requirement</th>
                <th>Status</th>
            </tr>
            <tr>
                <td style="font-weight: 600;">1. Problem Validated</td>
                <td>Is this a meaningful operational problem?</td>
                <td><span class="badge supported">Strongly Supported</span></td>
            </tr>
            <tr>
                <td style="font-weight: 600;">2. Data Validated</td>
                <td>Can we obtain real historical telemetry for simulation?</td>
                <td><span class="badge researching">Researching</span></td>
            </tr>
            <tr>
                <td style="font-weight: 600;">3. Forecasting Validated</td>
                <td>Is there a defensible prediction problem?</td>
                <td><span class="badge researching">Researching</span></td>
            </tr>
            <tr>
                <td style="font-weight: 600;">4. Architecture Validated</td>
                <td>Do the proposed technologies solve actual workload requirements?</td>
                <td><span class="badge open">Open</span></td>
            </tr>
             <tr>
                <td style="font-weight: 600;">5. End-to-End Validated</td>
                <td>Does the system emit accurate alerts?</td>
                <td><span class="badge not-started">Not Started</span></td>
            </tr>
        </table>
        
        <p class="intro-text"><strong>Next Decision Gate:</strong> Execute NOAA USCRN station audit and EDA to validate Gate 2.</p>

        <div class="section-header">
            <span class="section-number">05</span>
            <span class="section-title">Risks & Open Questions</span>
        </div>

        <p class="intro-text">
            <strong>Major Risks:</strong><br>
            - <em>False Alarms:</em> A pointwise prediction interval breach does not provide a sequence-wise false-alarm guarantee due to serial correlation.<br>
            - <em>Reanalysis Substitution Error:</em> Using ERA5-Land as an exact "ground truth" target prevents the realistic simulation of physical sensor anomalies.<br>
            - <em>Data Leakage:</em> Randomly distributing timestamps from a weather event across train/test sets leaks future information.
        </p>
        
        <p class="intro-text">
            <strong>Open Questions:</strong><br>
            - What is the actual decision cadence for the end user?<br>
            - How much forecast uncertainty can users accept before an alert becomes untrustworthy?<br>
            - Does the architecture genuinely require independent consumer replay (Kafka), or is Redis Streams sufficient?
        </p>

    </div>
</body>
</html>

```