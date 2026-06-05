# Performance Gap Analysis

**Date:** 2026-06-04

## Targets vs Status

| Target | Pre–Phase 4 | Post–Phase 4 (expected) | Gap |
|--------|-------------|-------------------------|-----|
| 100K < 1 s | ~1.7 s in-memory | ~1.0–1.5 s (projection) | Near |
| 100K spill+drill < 1 s | ~5–7 s | ~2–3 s (ARW1 + vector reconcile) | Improved |
| 1M < 5 s | Not tested | Requires benchmark | Open |
| 10M < 60 s | Not tested | Requires lazy scan spill | Open |
| 100 GB < 10 min | Not met | Needs distributed partitions | Large |
| 1000 columns | Not validated | Projection implemented | Test needed |
| 80 GB / 10 GB RAM | Not met | Streaming GCS + spill bounds | Large |

## Remaining Bottlenecks

1. **Full-file Polars load** for spill path — still O(file size) RAM during partition  
2. **DrilldownCache frames** — O(rows × compare_cols) for lazy path  
3. **Multi-char delimiter** — `flat_file` fallback remains CPU-heavy  
4. **No process pool** for partition reconcile — single-process per job  
5. **GCS prefetch default** — still downloads small files wholly  

## Closed Gaps (this phase)

| Gap | Fix |
|-----|-----|
| Python dict reconcile | Polars partition joins |
| Per-row spill encode | Arrow IPC batch |
| Full-partition payload decode | Fingerprint-only spill |
| Full-side drilldown dict | Batch key lookup |
| Wide column read | PyArrow `include_columns` |

## Measurement Commands

```bash
cd pegasus-backend
pytest tests/test_reconciliation_throughput.py -m performance -v
python ../scripts/benchmark_reconciliation.py
```
