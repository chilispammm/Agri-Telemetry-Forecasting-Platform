# Agri Telemetry & Forecasting Platform

**Operational time-series intelligence platform for root-zone soil water state estimation and threshold-crossing forecasting.**

---

## 1. Source of Truth Hierarchy

This repository is strictly evidence-driven and governed by the canonical Markdown specifications:

1. [`1. Project Charter/`](1.%20Project%20Charter) — Project Brief & Feasibility Boundaries
2. [`2. Research Feasibility/`](2.%20Research%20Feasibility) — In-Situ Soil Moisture & Telemetry Feasibility
3. [`3. Agents.md/`](3.%20Agents.md) — Engineering Constitution & Non-Negotiable Scientific Rules
4. [`4. Product Requirements Doc/`](4.%20Product%20Requirements%20Doc) — Product Requirements Document (PRD)
5. [`5. Data & Scientific Spec/`](5.%20Data%20%26%20Scientific%20Spec) — Scientific Meaning, Units & State Representation
6. [`6. Data Forecast Design/`](6.%20Data%20Forecast%20Design) — Horizon Targets, Persistence Benchmark & Uncertainty
7. [`7. Technical Spec/`](7.%20Technical%20Spec) — Subsystem Architecture & Ingress Pipeline
8. [`8. ADRs/`](8.%20ADRs) — Architecture Decision Records (ADR-001 through ADR-005)
9. [`9. Event & Telemetry Contract/`](9.%20Event%20%26%20Telemetry%20Contract) — Interface Contract & JSON Schemas (`schemas/`)
10. [`10. Implementation Plan/`](10.%20Implementation%20Plan) — 16-Module Vertical Slice Execution Roadmap
11. [`11. Evidence & Validation/`](11.%20Evidence%20%26%20Validation) — Master Validation Matrix & Experiment Ledger

---

## 2. Generating HTML Presentation Views

The HTML files across this repository are compiled presentation layers of the canonical Markdown files.

To regenerate all HTML presentation documents after updating any Markdown source, run:

```bash
python generate_html.py
```

*Zero external dependencies required (runs with standard Python 3.10+ library).*
