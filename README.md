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

## 2. Generating HTML Presentation Views

The HTML files across this repository are compiled presentation layers of the canonical Markdown files, featuring embedded MathJax LaTeX rendering and Mermaid SVG flowcharts.

To regenerate all HTML presentation documents after updating any Markdown source, run:

```bash
python generate_html.py
```

*Zero external dependencies required (runs with standard Python 3.10+ library).*
