# Bottleneck Analysis

**Date:** 2026-06-04  
**Symptom:** ~25 s for ~20–35 MiB CSV reconciliation  
**Root cause:** Optimized modules were not integrated into `TabularReconciliationPipeline.run()`

---

## Before vs After (100K rows, `||` delimiter, 33.5 MiB)

| Path | Before | After | Speedup |
|------|--------|-------|---------|
| Default (auto in-memory) | ~25 s* | **2.2 s** | **11×** |
| Forced disk spill | ~25 s | **3.7 s** | **6.8×** |
| 10K rows default | ~5 s* | **0.27 s** | **18×** |

\*Before = legacy `pipeline.py` (JSON spill + SHA256 + full-row drilldown payloads + sequential sides + scan all partition slots).

---

## Top 10 Slowest Functions (Before — cProfile, legacy spill)

| # | Function | cumtime | Issue |
|---|----------|---------|-------|
| 1 | `json.dumps` | ~8 s | Per-row spill encode |
| 2 | `json.loads` | ~3 s | Per-row reconcile decode |
| 3 | `_row_fingerprint` (SHA256) | ~1.2 s | Cryptographic hash per row |
| 4 | `_partition_side` loop | ~20 s | Dict-per-row + above |
| 5 | `_iter_data_rows` | ~0.5 s | Multi-char line parse |
| 6 | `_canonical` | ~0.7 s | Repeated per cell |
| 7 | `hashlib.sha256` | ~1.0 s | Fingerprint |
| 8 | `open`/`write` per row | ~0.3 s | Unbuffered (fixed) |
| 9 | Partition reconcile loop | ~2 s | Full partition scan 0..N |
| 10 | `dict` creation | ~2 s | `batch_to_dicts` |

## Top 10 Memory Consumers (After — 100K spill)

| # | Consumer | Peak | Notes |
|---|----------|------|-------|
| 1 | Polars DataFrame (source) | ~15 MiB | During partition |
| 2 | Polars DataFrame (target) | ~15 MiB | Parallel thread |
| 3 | Partition write buffers | ~256 KiB × buckets | Flushed at threshold |
| 4 | Reconcile `src_map` per partition | O(partition rows) | Cleared each partition |
| 5 | `bytearray` encode batches | Transient | Per partition group |
| 6 | PyArrow CSV batches | Chunked | Streaming fallback only |
| 7 | Sample mismatch list | &lt; 1 MiB | Capped at 1000 |
| 8 | Thread pool overhead | Minimal | 2 workers |
| 9 | Schema metadata | &lt; 1 KiB | |
| 10 | tracemalloc (benchmark only) | N/A | |

## Top 10 Disk Consumers

| # | Operation | Volume (100K spill) |
|---|-----------|---------------------|
| 1 | Spill write (source) | ~8 MiB |
| 2 | Spill write (target) | ~8 MiB |
| 3 | Spill read (reconcile) | ~16 MiB |
| 4 | CSV read | 8.4 MiB × 2 |
| 5 | Temp partition files | ~16 MiB peak |
| 6–10 | Metadata/fsync | Negligible |

## Top 10 Network Consumers

Local benchmarks: **0 B**. GCS path uses `open_gcs_binary` streaming; not profiled in this audit. See `OPTIMIZATION_PLAN.md` for GCS items.

---

## Critical Fixes Applied

| # | Bottleneck | Fix |
|---|-----------|-----|
| 1 | JSON spill in `pipeline.py` | Wire `spill.PartitionWriter` + binary `encode_record` |
| 2 | SHA256 fingerprints | Default `xxhash64` via `fingerprint.py` |
| 3 | Sequential source/target | `ThreadPoolExecutor(2)` |
| 4 | Scan all partition IDs | `list_partition_ids()` |
| 5 | Polars spill not used | `partition_side_polars` + `try_partition_side_polars` |
| 6 | `group_by` iteration bug | `partition_by("_pid")` |
| 7 | Full-row drilldown payload | `encode_compare_payload` (column-ordered binary) |
| 8 | Dict-per-row Polars build | Columnar lists in `_flat_parse_to_polars` |
| 9 | Redundant spill for small files | `polars_direct` before disk spill |
| 10 | Benchmark disabled Polars | `force_disk_spill` without zeroing `polars_spill_max_bytes` |

---

## Remaining Bottlenecks

| Priority | Issue | Impact | Plan |
|----------|-------|--------|------|
| P1 | Multi-char flat-file parse | ~1.5 s / 100K | CleverCSV batch or native extension |
| P2 | Drilldown disk spill | 2–10 s extra | Lazy drilldown on mismatch only |
| P3 | Python streaming fallback | 70+ s / 100K single-byte if Polars disabled | Never disable Polars spill in prod |
| P4 | Per-partition `iter_rows` encode | Drilldown serialization | Columnar bulk encode |
| P5 | GCS cold start | Variable | Prefix cache (exists), parallel range reads |
