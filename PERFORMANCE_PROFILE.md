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

## Stage Timings — In-Memory (`in_memory_polars`)

| Stage | Seconds | % |
|-------|---------|---|
| Source + target load (flat-file `||` parse) | ~1.3 | 75% |
| Polars joins + fingerprint | ~0.4 | 25% |
| **Total** | **~1.7** | 100% |

## Stage Timings — Spill + Drilldown (post-fix, 3-run median)

| Stage | Seconds | % |
|-------|---------|---|
| Source read (`_load_frame`) | 1.49 | 22% |
| Target read | 1.17 | 17% |
| Serialization (binary spill encode) | 3.87 | 56% |
| Disk read (reconcile) | 2.75 | 40% |
| Partition reconciliation | 2.84 | 41% |
| Column comparison | 0.06 | 1% |
| **Total wall** | **~6.9** | 100% |

*Read/partition stages overlap across 2 threads; percentages sum >100%.*

## Stage Timings — Spill, No Drilldown

| Stage | Seconds |
|-------|---------|
| Source read | 2.30 |
| Target read | 1.73 |
| Serialization | 2.32 |
| Reconciliation | 1.89 |
| **Total** | **~5.5** |

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
