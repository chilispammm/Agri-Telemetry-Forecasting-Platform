# ADR-005: MLOps & Experiment Tracking Scope

**Status:** DECIDED  
**Date:** 2026-09-30  
**Deciders:** Antigravity Team  
**Consulted:** PRD, Agents Constitution (Rule #19, #29)

---

## 1. Context & Problem Statement
Every experiment in the platform must be fully reproducible, tracking dataset version, temporal splits, feature definitions, hyperparameters, random seeds, and evaluation metrics. We must decide how to record this metadata.

## 2. Decision Drivers
- Rule #19: *"Every experiment must identify its context: dataset/source and version, time period, split strategy, horizon, features, target definition, model, metrics, code/version, and random seed."*
- Rule #15 & #16: Avoid deploying heavy external servers (like hosted MLflow or Kubeflow) unless strictly necessary.
- Local auditability and Git integration.

## 3. Considered Options
1. **Lightweight JSON & Markdown Experiment Ledger:** Local structured JSON experiment manifests committed alongside code, mirrored in `11. Evidence & Validation/Evidence & Validation - Agri Telemetry & Forecasting Platform.md`.
2. **Local SQLite MLflow Server:** MLflow tracking URI pointing to local `mlruns.db`.
3. **Cloud-Hosted Weights & Biases / Neptune.ai:** SaaS tracking requiring API keys and internet connectivity.

## 4. Decision Outcome
**Adopt a structured JSON & Markdown Experiment Ledger** embedded directly in the repository for Phase 1. An optional local MLflow logging adapter can be enabled via configuration if graphical metric curves are desired, but zero external SaaS dependencies are required.

### Positive Consequences:
- 100% offline reproducibility and version control with Git.
- Fast execution and simple inspection.
- No credential or port configuration friction.
