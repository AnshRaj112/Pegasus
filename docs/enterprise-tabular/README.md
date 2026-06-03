# Enterprise tabular reconciliation (Category-1)

Design and operations documentation for large-scale source/target tabular reconciliation inside **Pegasus**.

| Document | Topic |
|----------|--------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System layers, data flow, technology stack |
| [CATEGORY1_DESIGN.md](CATEGORY1_DESIGN.md) | Design principles and algorithms |
| [RECONCILIATION_FLOW.md](RECONCILIATION_FLOW.md) | Pipeline phases |
| [OPERATIONS_GUIDE.md](OPERATIONS_GUIDE.md) | Run Pegasus locally or with Docker |
| [PERFORMANCE_GUIDE.md](PERFORMANCE_GUIDE.md) | Tuning chunk size, partitions, memory |
| [SCALING_GUIDE.md](SCALING_GUIDE.md) | Horizontal scaling concepts |
| [KUBERNETES_GUIDE.md](KUBERNETES_GUIDE.md) | Optional K8s partition workers |

**Production code:** `pegasus-backend/src/pegasus/validation/` (six-stage `TabularReconciliationPipeline`).

**Reference prototype** (DB adapters, native columnar, spill, K8s worker entrypoint): `pegasus-backend/reference/category1_engine/`.

**UI:** `pegasus-frontend/` only.
