# ADR-003: Stream Processing & Buffer Architecture

**Status:** DECIDED  
**Date:** 2026-09-30  
**Deciders:** Antigravity Team  
**Consulted:** Agents Constitution (Rule #15, #16)

---

## 1. Context & Problem Statement
The platform processes sequential telemetry events, performs QC filtering, triggers forecasting, and computes risk alerts. We need to decide whether to introduce a distributed streaming engine (e.g. Kafka, Redis Streams) or a lightweight local queue.

## 2. Decision Drivers
- Adherence to Rule #15 ("Do not add infrastructure merely because it demonstrates a technology").
- Adherence to Rule #16 ("MQTT, Redis Streams, Kafka, RabbitMQ require explicit justification").
- Low data velocity (hourly measurements across agricultural fields do not require millions-of-events/sec distributed streaming).
- Deterministic walk-forward replay capability.

## 3. Considered Options
1. **Lightweight In-Memory Event Queue / Worker Dispatcher:** Python queue with idempotent key indexing and SQLite persistence.
2. **Redis Streams:** Lightweight distributed stream broker with consumer groups.
3. **Apache Kafka / RabbitMQ:** Heavy distributed message logs with Zookeeper/KRaft.

## 4. Decision Outcome
**Adopt a Lightweight In-Memory / Local Worker Queue with Idempotency Key Tracking** for Phase 1. Redis Streams is defined as the clean upgrade path for Phase 2 distributed scaling. Kafka is explicitly rejected as unnecessary over-engineering.

### Positive Consequences:
- Zero container or infrastructure overhead for running the entire test suite and reproducibility benchmarks.
- Clean separation of concerns via event interfaces.
- Fully deterministic backtesting and walk-forward evaluations.
