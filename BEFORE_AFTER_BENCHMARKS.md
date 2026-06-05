# Before / After Benchmarks

**Host:** Linux, Polars 1.40.1  
**Fixtures:** `generated-10k-8cols`, `generated-100k-8cols`, UID `id`, delimiter `||`, 7 compare columns

## Summary

| Workload | Metric | Before | After | Δ |
|----------|--------|--------|-------|---|
| 10K | `ValidationService` wall | ~8–28 s (API) / ~1.4 s (service) | **0.31 s** | **~4–90×** |
| 10K | Pipeline only | ~8 s (spill) | **0.33 s** (in_memory) | **~24×** |
| 100K | Service wall | ~10–16 s | **1.41 s** | **~7–11×** |
| 100K | Pipeline auto | ~3.3 s (spill) | **1.25 s** (in_memory) | **~2.6×** |
| 100K | Spill + drilldown | ~7–12 s | **2.4–3.2 s** | **~2–4×** |
| 100K | Load parse only | ~670 ms | **~120 ms** | **~5.5×** |

## Detailed Runs (after optimization)

### `ValidationService._validate_csv_pair_sync`

| Rows | Wall (s) | Rows/s | Path |
|------|----------|--------|------|
| 10,000 | 0.31 | 32,258 | `in_memory_polars` |
| 100,000 | 1.41 | 70,922 | `in_memory_polars` |

### `TabularReconciliationPipeline` (direct)

| Rows | Config | Wall (s) | Path |
|------|--------|----------|------|
| 10,000 | auto | 0.33 | `in_memory_polars` |
| 100,000 | auto | 1.25 | `in_memory_polars` |
| 100,000 | `force_disk_spill` + drilldown | 2.45–3.22 | `spill_arrow_ipc` |

### Harness `scripts/benchmark_reconciliation.py` (pipe `|`, 11 compare cols)

| Rows | Mode | Wall (s) | Rows/s |
|------|------|----------|--------|
| 10,000 | auto | 0.42 | 23,569 |
| 10,000 | spill | 0.16 | 62,971 |
| 100,000 | auto | 0.36 | 274,414 |
| 100,000 | spill | 0.60 | 166,874 |

## Resource Profile (100K in-memory)

| Resource | Before (spill) | After (in-memory) |
|----------|----------------|-------------------|
| CPU | ~2 s wall, low utilization | ~1 s, 1–2 cores busy |
| Memory | Spill files + dict temps | ~40 MiB peak (2× file) |
| Disk | Read+write spill | Read only |
| Network | — | — |

## Target Checklist

| SLO | Result |
|-----|--------|
| 10K &lt; 1 s | ✓ 0.31 s |
| 100K &lt; 3 s | ✓ 1.41 s |
| 1M &lt; 10 s | Pending full run |
| 10M &lt; 60 s | Needs streaming (Phase 2) |

## Docker (after env + worker pool)

Rebuild and restart:

```bash
docker compose up --build -d
```

Expected: 100K `||` local job **&lt;5s** worker total (first job may be ~6–8s while pool warms; second job **&lt;3s**).

## How to Reproduce

```bash
PYTHONPATH=pegasus-backend/src python3 scripts/benchmark_reconciliation.py --sizes 10000,100000
PYTHONPATH=pegasus-backend/src python3 -m pytest pegasus-backend/tests/test_reconciliation_throughput.py -m performance
```
