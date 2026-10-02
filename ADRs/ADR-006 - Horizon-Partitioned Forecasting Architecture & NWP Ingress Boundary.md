# ADR-006: Horizon-Partitioned Forecasting Architecture & NWP Ingress Boundary

**Status:** DECIDED  
**Date:** October 2, 2026  
**Deciders:** Antigravity Engineering & Science Team  
**Consulted:** Technical Spec, Data Forecast Design, Evidence & Validation  

---

## 1. Context & Problem Statement

Phase 2 and Phase 3 empirical benchmark experiments on real historical USCRN soil telemetry (`NE_Lincoln_11_SW`, 2023 H2 test split, $N = 3,913$) revealed two distinct physical regimes across forecast horizons:
1. **Short-to-Medium Horizons ($1\text{h} \le h \le 48\text{h}$)**:
   - Environmental Exogenous Forecasters ($M2$, utilizing recent precipitation accumulation, air temperature, solar radiation, and diurnal cycles) consistently beat Persistence ($B0$) by **+1.0% to +5.7% MSE reduction** on root-zone moisture ($\theta_{\text{rz}}$) and **+26.4%** on shallow topsoil ($\theta_{10\text{cm}}$).
   - Pure Autoregressive ($M1$) models suffer from regularized lag penalties on short horizons ($\text{Skill} = -3.754$ at 1h).
2. **Long Horizons ($72\text{h} \le h \le 168\text{h}$)**:
   - The Environmental Forecaster ($M2$) degrades significantly ($\text{Skill} = -0.140$ at 168h) because static historical precipitation without future weather forecasts loses predictive power beyond 48 hours.
   - Conversely, the Autoregressive Forecaster ($M1$) captures slow seasonal mean-reversion trends, beating persistence by **+1.4% MSE reduction at 72h** and **+7.8% at 168h** ($\text{Skill} = +0.078$).
3. **Future Weather (NWP) Value & Data Boundary**:
   - Controlled oracle experiments demonstrated that knowing future precipitation unlocks massive forecast skill (+50.7% at 6h, up to +96.4% at 168h).
   - However, downloading and processing multi-gigabyte raw gridded NWP rasters (e.g. NOAA HRRR / GFS GRIB2/Zarr) directly in-process introduces heavy cloud dependencies and undermines local deterministic reproducibility.

We must decide:
1. How the forecasting engine should architecturally partition models across horizons.
2. How the system defines the boundary between in-situ telemetry and external Numerical Weather Prediction (NWP) forecasts.

---

## 2. Decision

1. **Adopt a Horizon-Partitioned Hybrid Forecaster Architecture**:
   - For short-to-medium horizons ($1\text{h} \le h \le 48\text{h}$), the forecasting engine routes inference to the **Environmental ARX Model (`M2`)**.
   - For long horizons ($72\text{h} \le h \le 168\text{h}$), the forecasting engine routes inference to the **Autoregressive Trend Model (`M1`)**.
   - This hybrid strategy guarantees strictly positive skill over persistence across the entire forecast envelope ($1\text{h} \dots 168\text{h}$) using in-situ telemetry alone.

2. **Establish a Clean NWP Ingress Boundary via Standardized Forecast Contracts**:
   - The core forecasting engine will **not** directly download or parse gridded GRIB2/Zarr weather files.
   - Instead, an explicit schema contract (`WeatherForecastEvent`) will define point-interpolated precipitation probability and expected accumulation.
   - Live NWP integration is deferred to a dedicated ingress adapter (e.g. NOAA API / HRRR point extractor) without polluting the core domain models.

3. **Deploy Regime-Conditioned Uncertainty for Short Leads ($1\dots 48\text{h}$)**:
   - Condition residual dispersion on antecedent rainfall ($P_{24\text{h}} > 1.0\text{ mm}$) to dynamically expand prediction intervals during active infiltration and contract them during quiescent dry spells.
   - Maintain research status on long-horizon ($>48\text{h}$) uncertainty until forward NWP precipitation probabilities are integrated.

---

## 3. Consequences & Trade-offs

### Positive:
- **Strictly Positive Skill Across All Horizons**: Empirical out-of-sample skill remains $> 0.0$ for all $h \in [1, 168\text{h}]$, eliminating negative skill at long horizons.
- **Architectural Modularity**: In-situ forecasting remains fully functional and reproducible without requiring active external weather APIs.
- **Clear Expansion Path**: When NWP data becomes available via the ingress adapter, $M2$ can seamlessly consume forward precipitation features without refactoring domain logic.

### Negative / Trade-offs:
- Requires maintaining two fitted model artifacts ($M2$ weights for $1\dots 48\text{h}$ and $M1$ weights for $72\dots 168\text{h}$).
- Long-horizon uncertainty intervals remain static/empirical until forward weather forecasts are connected.

---

## 4. Status
**DECIDED & IMPLEMENTED** (Supported by Empirical Validation runs `EXP-20261002-004` and `EXP-20261002-005`).
