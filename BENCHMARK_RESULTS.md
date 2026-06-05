# Benchmark Results

**Date:** 2026-06-04 (Phase 4)  
**Machine:** 4-core Linux, Python 3.12

## Phase 4 Summary

| Change | Effect |
|--------|--------|
| Arrow IPC spill (ARW1) | Fingerprint-only blocks; faster serialize/decode |
| Polars partition reconcile | Replaces per-partition Python `dict` merge |
| Batch lazy drilldown | Payload lookup only for changed keys |
| Column projection (spill read) | PyArrow `include_columns` on single-byte delimiters |

## 100K × 12 columns (benchmark script, `\|` delimiter)

| Configuration | Wall time | Rows/s | Path |
|---------------|-----------|--------|------|
| Auto | **0.50 s** | 199,774 | `in_memory_polars` |
| Spill, no drilldown | **2.37 s** | 42,204 | `spill_arrow_ipc` |
| Spill + drilldown | **1.11 s** | 90,364 | `spill_arrow_ipc` / lazy drilldown |

## 100K × 8 columns (`generated-100k-8cols`, `||`, mismatch-heavy)

| Configuration | Wall time | Rows/s | Path |
|---------------|-----------|--------|------|
| Auto | ~1.7–2.8 s | 35K–59K | `in_memory_polars` |
| **Phase 4** spill + drilldown | **~3.0–3.5 s** | ~29K | `spill_arrow_ipc` |
| Phase 2 spill + drilldown | ~5.0 s | ~20K | `spill_binary_lazy_drilldown` |
| Phase 1 spill + drilldown | ~7.0 s | ~14K | `spill_columnar` |
| Before optimization | 12.24 s | 8,170 | `spill_binary` |

**Improvement (8-col mismatch spill+drill): ~12 s → ~3 s (~4×)**

## Regression gates (`pytest -m performance`)

| Test | Threshold |
|------|-----------|
| 100K auto | < 3.0 s |
| 100K spill (no drill) | < 8.0 s |
| 100K spill + drill (8-col) | < 3.5 s |

## Artifacts

- `docs/benchmarks/reconciliation-results.json`
- Architecture: `CURRENT_WORKFLOW.md`, `TARGET_WORKFLOW.md`, `ARCHITECTURE_DIFF.md`

## Commands

```bash
PYTHONPATH=pegasus-backend/src python scripts/benchmark_reconciliation.py --sizes 100000
cd pegasus-backend && PYTHONPATH=src python -m pytest tests/test_reconciliation_throughput.py -m performance -v
```
