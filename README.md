# Agri Telemetry & Forecasting Platform

**Operational time-series intelligence platform for root-zone soil water state estimation and threshold-crossing forecasting.**

---

## 1. Repository Architecture & Source of Truth

This repository is strictly evidence-driven and structured into canonical specification and engineering layers:

* [`Project Charter/`](Project%20Charter) — Project Charter & Strategic Foundations
* [`Research Feasibility/`](Research%20Feasibility) — In-Situ Soil Moisture & Telemetry Research Feasibility
* [`Product Requirements Doc/`](Product%20Requirements%20Doc) — Product Requirements Document (PRD)
* [`Data & Scientific Spec/`](Data%20%26%20Scientific%20Spec) — Scientific Meaning, Physical Units & State Representation
* [`Data Forecast Design/`](Data%20Forecast%20Design) — Horizon Targets, Persistence Benchmark & Uncertainty Framework
* [`Technical Spec/`](Technical%20Spec) — Subsystem Architecture, Ingress Pipeline & Component Topology
* [`ADRs/`](ADRs) — Architecture Decision Records (ADR-001 through ADR-005 + Master Register)
* [`Event & Telemetry Contract/`](Event%20%26%20Telemetry%20Contract) — Interface Contract & Strict JSON Schemas (`schemas/`)
* [`Implementation Plan/`](Implementation%20Plan) — 16-Module Vertical Slice Execution Roadmap
* [`Evidence & Validation/`](Evidence%20%26%20Validation) — Master Validation Matrix & Empirical Verification Ledger

---

## 2. Phase 1 Minimum Reproducible Vertical Slice

The Phase 1 Python package (`agri_telemetry/`) executes the full end-to-end scientific pipeline:

```text
REAL HISTORICAL TELEMETRY (USCRN Hourly)
        ↓
NORMALISE INTO EVENT CONTRACT (TelemetryEvent)
        ↓
JSON SCHEMA VALIDATION (Draft 2020-12)
        ↓
TIER-1 QUALITY CONTROL (Range, Spike, Stuck, Quarantine Buffer)
        ↓
STATE CONSTRUCTION (Depth-weighted θ_rz, Dr, FAW, Storage mm)
        ↓
PERSISTENCE FORECAST (Ŷ_{t+h|t} = Y_t Baseline for h ∈ {1..168h})
        ↓
BASELINE UNCERTAINTY (Empirical walk-forward residual quantiles)
        ↓
CONFIGURABLE RISK EVALUATION (3-Tier isolation, MAD & Wilting thresholds)
        ↓
FORECAST / ADVISORY EVENT (ForecastEvent & Non-actuating AlertEvent)
        ↓
STORED RUN + EVIDENCE (SQLite & Evidence Ledger)
```

---

## 3. Quick Start & Execution

### Running the Phase 1 Vertical Slice
To execute the pipeline on the full-year 2023 USCRN historical dataset (8,760 hourly records):

```bash
python -m agri_telemetry run-phase1
```

### Auditing Data Quality
To inspect coverage, cadence, missingness, and variable ranges for a dataset:

```bash
python -m agri_telemetry audit --file data/uscrn/CRNH0203-2023-NE_Lincoln_11_SW.txt
```

### Running the Test Suite
To run the full unit and integration test suite across all 28 test cases:

```bash
python -m pytest -v
```

---

## 4. Generating HTML Presentation Views

The HTML files across this repository are compiled presentation layers of the canonical Markdown files, featuring embedded MathJax LaTeX rendering and Mermaid SVG flowcharts.

To regenerate all HTML presentation documents after updating any Markdown source, run:

```bash
python generate_html.py
```

*Zero external dependencies required (runs with standard Python 3.10+ library).*
