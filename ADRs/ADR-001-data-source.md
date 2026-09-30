# ADR-001: Primary Data Source & In-Situ Research Network Selection

**Status:** DECIDED  
**Date:** 2026-09-30  
**Deciders:** Antigravity Team  
**Consulted:** Scientific Spec, Research Feasibility

---

## 1. Context & Problem Statement
The platform requires continuous, high-fidelity historical in-situ soil moisture and micrometeorological telemetry to train, benchmark, and validate forecasting models. We must decide on the initial primary data source without relying on synthetic pure-random generators or inaccessible proprietary farm hardware.

## 2. Decision Drivers
- Multi-depth volumetric water content ($\text{m}^3/\text{m}^3$) availability (5cm, 10cm, 20cm, 50cm, 100cm).
- Collocated meteorological measurements (air temp, relative humidity, precipitation, solar radiation, wind).
- Public accessibility, rigorous calibration, and complete provenance.
- Hourly/sub-hourly temporal resolution over multi-year records.

## 3. Considered Options
1. **USCRN (U.S. Climate Reference Network) / SCAN:** Standardized, calibrated, triple-redundant in-situ soil moisture probes with complete weather station records.
2. **ERA5-Land / Open-Meteo Reanalysis:** Modeled spatial grids (violates Rule #4 if treated as ground-truth observation).
3. **Pure Synthetic Simulation:** Random walk generators (violates Rule #3 if presented as real telemetry).

## 4. Decision Outcome
**Adopt USCRN / SCAN station archives** as the canonical observed in-situ data source for platform benchmarking and replay simulation.

### Positive Consequences:
- Real physical dynamics (precipitation infiltration, diurnal ET drying curves, seasonal transitions).
- Exact provenance tracking and adherence to Rule #4.
- Enables reproducible walk-forward evaluation.

### Negative Consequences / Mitigations:
- Station-specific soil texture and hydraulic properties must be documented rather than assumed to be universally transferable.
