# Bottleneck Analysis

**Date:** 2026-06-04

## Root Causes (ranked)

### 1. Wrong execution path — silent in-memory failure (FIXED)

**Symptom:** ~16–48 s for 100K rows on a ~20 MiB file.  
**Cause:** `try_in_memory_reconcile` caught `ColumnNotFoundError` when `compare_columns` listed columns not in the file (e.g. 11 configured, 8 present). Pipeline fell back to per-row streaming spill.  
**Fix:** `filter_compare_columns()` at pipeline entry and in `try_in_memory_reconcile`.  
**Impact:** Restores **~1.7 s** auto path when schema-aligned.

### 2. Per-row spill serialization with drilldown (PARTIALLY FIXED)

**Symptom:** ~12 s → still ~7 s on mismatch-heavy 100K.  
**Cause:** `_write_frame_partitions` Python loop: `encode_record` + `encode_compare_payload` per row (~170K records).  
**Fix:** `encode_compare_payload_values` (no dict), canonicalize in Polars before encode.  
**Remaining:** Still O(rows) Python loop; needs columnar batch encoder.  
**Expected further gain:** 2–3× on drilldown spill.

### 3. Multi-character delimiter parse (OPEN)

**Symptom:** ~1.3 s per side to load 10 MiB CSV.  
**Cause:** `flat_file.parse_lines` + Python list → Polars (PyArrow/Polars cannot use `||` as single-byte delimiter).  
**Options:** Rust extension, `clevercsv` streaming, memory-mapped line scan.  
**Not GCS-bound** for local files.

### 4. Reconciliation dict build (MODERATE)

**Symptom:** ~2.8 s disk read + reconcile on 100K mismatches.  
**Cause:** Load entire partition into `dict[key → (fp, payload)]` even when most rows only need fingerprint.  
**Options:** Two-pass reconcile; store payload only for inner-join keys; streaming merge sort.

### 5. Streaming fallback path (WHEN TRIGGERED)

**Symptom:** 50–100+ s on 100K rows.  
**Cause:** `row_fingerprint_bytes` + `canonical` × columns × rows; `batch_to_dicts`; MD5 partition (now xxhash).  
**Mitigation:** Ensure Polars spill path; fused canonical in streaming (FIXED).

## What is NOT the bottleneck

| Suspected | Evidence |
|-----------|----------|
| SHA256 fingerprint | Default is `xxhash64`; vectorized Polars `hash()` on fast path |
| JSON spill | Removed from hot path; binary `CB\x01` payload |
| GCS (with prefetch) | Mock test: 2 downloads, **~1.7 s** same as local in-memory |
| Disk I/O (NVMe) | Buffered 256 KiB writes; spill files ~few MiB |
| Partition count | Adaptive buckets (16 for &lt;4 MiB class after size adjust) |

## Profiling Evidence (cProfile, streaming fallback — worst case)

Top self-time consumers:

1. `row_fingerprint_bytes` / `_fingerprint_xxhash64` — 67 s cumulative (100K, forced streaming)
2. `PartitionWriter.write` / `encode_compare_payload` — 19 s
3. `canonical` — 3.9M calls
4. `csv.reader` / `_iter_data_rows` — 12 s

After Polars spill path: fingerprint/canonical drop to **0 s** in stage timers.

## Fix Status

| Fix | Status |
|-----|--------|
| Wire binary spill + timing | Done (prior pass) |
| `filter_compare_columns` | **Done** |
| Fused canonical streaming | **Done** |
| `encode_compare_payload_values` | **Done** |
| Polars canonical before spill payload | **Done** |
| `partition_id` xxhash | **Done** |
| Columnar batch spill encoder | Planned |
| Lazy drilldown payload | Planned |
