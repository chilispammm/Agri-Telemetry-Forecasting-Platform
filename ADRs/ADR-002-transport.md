# ADR-002: Event Ingestion Transport Protocol

**Status:** DECIDED  
**Date:** 2026-09-30  
**Deciders:** Antigravity Team  
**Consulted:** PRD, Technical Spec

---

## 1. Context & Problem Statement
The platform must ingest sensor telemetry from field data loggers and historical replay workers. We need to decide on the network transport protocol for the minimal vertical slice.

## 2. Decision Drivers
- Simplicity and testability (Rule #18).
- Minimal external runtime dependencies.
- Strict schema validation support.
- Compatibility with standard HTTP clients and local file replays.

## 3. Considered Options
1. **HTTP/1.1 REST (JSON):** Standard stateless HTTP POST endpoints and direct in-process Python callable handlers.
2. **MQTT (Message Queuing Telemetry Transport):** Lightweight IoT broker protocol requiring an active broker daemon (e.g. Mosquitto).
3. **gRPC / Protocol Buffers:** High-performance binary serialization requiring protobuf compilation.

## 4. Decision Outcome
**Adopt HTTP REST (JSON) and direct in-memory event dispatch** for the Phase 1 implementation. MQTT integration is documented as an ingress adapter pattern to be introduced only when physical field gateways are connected in Phase 2/3.

### Positive Consequences:
- Zero external daemon requirements for unit/integration testing.
- Direct JSON schema validation against `telemetry-event.schema.json`.
- Rapid developer setup and high execution reliability.

### Negative Consequences:
- Higher payload overhead compared to binary protobufs, which is acceptable given hourly telemetry volumes.
