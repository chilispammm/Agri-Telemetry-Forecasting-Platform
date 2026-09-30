# ADR-004: Mandatory Forecasting Baseline & Benchmark Hierarchy

**Status:** DECIDED  
**Date:** 2026-09-30  
**Deciders:** Antigravity Team  
**Consulted:** Data Forecast Design (Rule #7, #8, #9, #10)

---

## 1. Context & Problem Statement
Machine learning time-series models can easily overfit or produce misleading validation metrics if not rigorously benchmarked against persistence baselines under leak-free temporal splitting.

## 2. Decision Drivers
- Non-negotiable Rule #7: *"Persistence is the mandatory baseline for forecasting experiments."*
- Rule #8: *"Use chronological or walk-forward evaluation for time-series forecasting."*
- Rule #9: *"Never use random train/test splitting."*
- Rule #10: *"Separate point forecasting from probabilistic forecasting."*

## 3. Considered Options
1. **Persistence Baseline + Empirical Quantile Residuals:** $\hat{Y}_{t+h|t} = Y_t$, with error quantiles derived from historical walk-forward residuals.
2. **Autoregressive / GBDT (e.g. LightGBM/HistGradientBoosting):** Multi-horizon lagged feature regressors.
3. **Deep Sequence Models (LSTM / Temporal Fusion Transformers):** High-parameter neural networks.

## 4. Decision Outcome
**Adopt Persistence Baseline as the non-negotiable benchmark.** Every candidate model class (e.g. Ridge Regression, GBDT) must be evaluated against this baseline across horizons $h \in \{6, 12, 24, 48, 72, 168\}\text{ hours}$. A candidate model is approved for deployment only if it demonstrates statistically significant and reproducible improvement over persistence under chronological walk-forward evaluation.

### Positive Consequences:
- Prevents premature adoption of unvalidated complex architectures.
- Establishes a crystal-clear metric bar for forecasting utility.
- Guarantees transparency and leak-free temporal evaluation.
