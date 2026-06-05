# Performance Profile

**Date:** 2026-06-04  
**Host:** Linux 5.15, 4 CPU cores, Python 3.12  
**Primary dataset:** `test-data/generated-100k-8cols` (100K + 70K rows, 8 columns, 7 compare, ~20.8 MiB)

## Before / After (this optimization pass)

| Scenario | Before | After | Speedup |
|----------|--------|-------|---------|
| Auto path (in-memory Polars) | ~1.8 s | **~1.7–1.9 s** | ~1× (already fast) |
| Disk spill, no drilldown | ~2.9 s | **~2.9–3.0 s** | ~1× |
| Disk spill + drilldown (mismatch-heavy) | **~12.2 s** | **~6.8–7.0 s** | **~1.75×** |
| Profile harness (11 cols on 8-col file, spill+drill) | **~16.9 s** (user) / ~16–22 s | **~7 s** (filtered cols) | **~2.4×** |

Historical: user reported **~28.3 s → ~16.9 s** before this pass (integration of binary spill + Polars). Combined with this pass: **~28.3 s → ~7 s** on spill+drill for the same workload class.

## Stage Metrics — In-Memory (`in_memory_polars`)

Approximate rollup (100K `||` 8-col):

```
Read Source:       Wall ~1.3 s   CPU ~1.2 s   Read ~12 MiB   Written 0
Partition Source:  Wall ~0.0 s   CPU ~0.0 s   Read 0         Written 0
Read Target:       Wall ~0.0 s   CPU ~0.0 s   Read ~8 MiB    Written 0
Partition Target:  Wall ~0.0 s   CPU ~0.0 s   Read 0         Written 0
Reconciliation:    Wall ~0.4 s   CPU ~0.4 s   Read 0         Written 0
Report:            Wall ~0.0 s   CPU ~0.0 s   Read 0         Written 0
Total:             Wall ~1.7 s   CPU ~1.6 s
```

## Stage Metrics — Spill + Drilldown (post-fix, 3-run median)

```
Read Source:       Wall 1.49 s   CPU ~1.4 s   Read ~12 MiB   Written 0
Partition Source:  Wall ~2.4 s   CPU ~2.3 s   Read 0         Written ~1.7 MiB
Read Target:       Wall 1.17 s   CPU ~1.1 s   Read ~8 MiB    Written 0
Partition Target:  Wall ~2.7 s   CPU ~2.5 s   Read 0         Written ~1.2 MiB
Reconciliation:    Wall 2.84 s   CPU ~2.5 s   Read ~2.9 MiB  Written 0
Report:            Wall 0.00 s   CPU 0.00 s   Read 0         Written 0
Total:             Wall ~6.9 s   CPU ~7 s
```

*Read/partition wall times overlap across two threads; Total wall is end-to-end.*

## Stage Metrics — Spill, No Drilldown

```
Read Source:       Wall 2.30 s
Partition Source:  Wall ~0.5 s (spill encode)
Read Target:       Wall 1.73 s
Partition Target:  Wall ~0.6 s
Reconciliation:    Wall 1.89 s
Total:             Wall ~5.5 s
```

Live metrics: `result.extra_stats["stage_report"]` or `pipeline_metadata.stage_report` on validation responses.

## Category Breakdown

| Category | Measured (spill+drill) | Notes |
|----------|------------------------|-------|
| File open | &lt; 0.01 s | Partition handles lazily opened |
| File read | ~2.7 s | Multi-char flat parse → Polars |
| Network | 0 s (local) | GCS mock cached: ~1.7 s total |
| Parse | Included in read | Not separate PyArrow for `\|\|` |
| Canonicalization | 0 s (vectorized) | Polars `_canonical_expr` |
| Identity generation | 0 s (vectorized) | `concat_str` |
| Fingerprint | 0 s (vectorized) | Polars `hash()` |
| Partition calculation | 0 s (vectorized) | `hash() % N` |
| Partition write | Included in serialization | 256 KiB buffered flush |
| Partition read | ~2.75 s | `iter_partition` decode |
| Reconciliation | ~2.84 s | Dict merge per partition |
| Column comparison | ~0.06 s | Only on fingerprint mismatch |
| Report generation | &lt; 0.001 s | Optional markdown |
| Serialization | ~3.9 s | Per-row `encode_record` in Python loop |
| JSON (hot path) | 0 s | Binary spill only |
| GC / allocation | Not profiled separately | ~40 MiB peak spill path |

## Profiling Commands

```bash
PYTHONPATH=pegasus-backend/src python scripts/profile_pipeline.py \
  --source test-data/generated-100k-8cols/source.csv \
  --target test-data/generated-100k-8cols/target.csv \
  --force-spill

PYTHONPATH=pegasus-backend/src python scripts/benchmark_reconciliation.py --sizes 100000
PYTHONPATH=pegasus-backend/src python scripts/generate_top50_functions.py
```

## Path Selection (current)

```
combined_bytes ≤ 256 MiB  →  in_memory_polars (~1.7 s)
force_disk_spill          →  spill_binary (3–7 s)
identical files           →  precheck / merkle (ms)
```
