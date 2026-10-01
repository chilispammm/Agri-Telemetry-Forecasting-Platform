## Run Execution `RUN-20261001-152227-10fc74`
- **Executed At (UTC)**: `2026-10-01T15:22:27.848577`
- **Dataset**: `CRNH0203-2023-NE_Lincoln_11_SW` (`USCRN_NE_Lincoln_11_SW`)
- **Time Range**: `2023-01-01T01:00:00+00:00` to `2024-01-01T00:00:00+00:00`
- **Total Ingested Records**: `8,760`
- **Valid Events**: `7,826`
- **Quarantined Events**: `880`
- **Emitted Forecast Events**: `3,913`
- **Emitted Alert Events**: `3728` (Autonomous Actuation: **False**)

### Out-of-Sample Persistence Benchmark Metrics
| Horizon | MAE (m³/m³) | RMSE (m³/m³) | 80% PI Coverage | Skill vs Climatology |
| :--- | :--- | :--- | :--- | :--- |
| `1h` | 0.0007 | 0.0024 | 85.5% | +0.998 |
| `6h` | 0.0018 | 0.0065 | 81.9% | +0.986 |
| `12h` | 0.0028 | 0.0091 | 82.3% | +0.972 |
| `24h` | 0.0047 | 0.0123 | 72.7% | +0.950 |
| `48h` | 0.0079 | 0.0166 | 69.8% | +0.909 |
| `72h` | 0.0109 | 0.0198 | 68.6% | +0.870 |
| `168h` | 0.0192 | 0.0283 | 60.9% | +0.742 |

---

