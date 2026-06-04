# Hot Path Analysis

**Date:** 2026-06-04  
**Dataset:** `test-data/generated-100k-8cols` (100K source / 70K target, `||` delimiter, ~20.8 MiB combined, 7 compare columns)

## Executive Summary

Production validation for sub-256 MiB delimited pairs should take the **Polars in-memory join** path (~1.7–2.0 s for 100K rows). The ~16.9 s figure matches **forced disk spill + column drilldown** on mismatch-heavy workloads (~12–22 s before optimization, **~7 s after** this pass).

## Request → Implementation Trace

### A. API / Service Path (local CSV)

| Step | Component | Function | CPU | Memory | Disk | Network |
|------|-----------|----------|-----|--------|------|---------|
| 1 | `ValidationService` | `_validate_csv_pair_sync` → `_validate_delimited_adapters_sync` | Low | Low | — | — |
| 2 | Delimiter | `resolve_delimiter_for_adapters` | Low | — | — | — |
| 3 | GCS prefetch (if cloud) | `prefetch_gcs_delimited_pair` | Low | Cache bytes | — | **GCS download** |
| 4 | Schema | `FileDelimitedAdapter.get_schema` | Low | Header row | Read | — |
| 5 | Budget | `plan_workload_budget` → `TabularPipelineConfig` | Low | — | — | — |
| 6 | Pipeline | `TabularReconciliationPipeline.run` | **Hot** | **Hot** | Spill dir | — |
| 7 | Results | `pipeline_result_to_run_result` | Low | Low | — | — |

### B. Pipeline `run()` Decision Tree

```
TabularReconciliationPipeline.run
├─ try_identical_precheck (Merkle / metadata)     → early exit if identical
├─ should_try_in_memory_reconcile (size ≤ auto_in_memory_max_bytes)
│  └─ try_in_memory_reconcile                     → path: in_memory_polars  ★ DEFAULT FAST
├─ polars_direct (size ≤ polars_spill_max_bytes, not forced spill)
│  └─ try_in_memory_reconcile                     → path: polars_direct
└─ Disk spill (ThreadPoolExecutor × 2)
   ├─ _partition_side (source)
   │  ├─ partition_side_polars (single-byte delim + PyArrow)
   │  ├─ try_partition_side_polars (_load_frame → Polars vectorized)  ★ multi-char delim
   │  └─ _partition_side_streaming (per-row dict + xxhash)             ★ fallback slow
   ├─ _partition_side (target)  [same]
   ├─ spill_partitions_identical (optional Merkle on spill files)
   └─ Per-partition reconcile
      ├─ iter_partition (binary decode)
      ├─ dict[key] → fingerprint compare
      └─ column drilldown (payload dict compare) if enabled
```

### C. In-Memory Fast Path (measured ~1.7 s)

| Step | Function | Sub-functions | CPU | Memory | Disk | Network |
|------|----------|---------------|-----|--------|------|---------|
| Load source | `_load_frame` → `_load_delimited_frame` | `_flat_parse_to_polars` or `read_csv_table` | **High** | **~2× file size** | — | GCS if cached |
| Load target | same | parallel `ThreadPoolExecutor(2)` | **High** | same | — | — |
| Fingerprint | `_fingerprint_expr` | Polars `concat_str` + hash | Medium | Columnar | — | — |
| Missing | `join(how="anti")` | Polars | Medium | — | — | — |
| Extra | `join(how="anti")` | Polars | Medium | — | — | — |
| Changed | `inner` + `filter(_fp != _fp_tgt)` | Polars | Medium | — | — | — |
| Samples | `iter_rows` (cap 1000) | Python | Low | — | — | — |

### D. Disk Spill + Drilldown Path (measured ~7 s post-fix)

| Step | Function | CPU | Memory | Disk | Network |
|------|----------|-----|--------|------|---------|
| Read + vectorize | `try_partition_side_polars` | **~2.5 s** | DataFrame | — | — |
| Identity / FP / partition | `_identity_expr`, `_fingerprint_expr`, `_partition_expr` | In Polars | — | — | — |
| Serialize spill | `_write_frame_partitions` → `encode_record` + `encode_compare_payload_values` | **~3.6–4.2 s** | Buffers | **Write `part_*.bin`** | — |
| Reconcile | `iter_partition` + dict merge | **~2.8 s** | Per-partition dicts | **Read spill** | — |
| Column compare | per-cell on mismatch only | ~0.06 s | — | — | — |

### E. Streaming Fallback (single-byte delim or Polars load failure)

| Step | Function | CPU | Memory | Disk |
|------|----------|-----|--------|------|
| Read | `FileDelimitedAdapter.stream_records` → PyArrow batches → `batch_to_dicts` | High | dict/row | — |
| Per row | `canonical` ×2, `row_fingerprint_from_parts`, `partition_id`, `PartitionWriter.write` | **Very high** | dict churn | Buffered spill |

## Path Selection Rules

| Condition | Path | 100K `||` timing |
|-----------|------|------------------|
| Combined size ≤ `validation_auto_in_memory_max_bytes` (256 MiB default) | `in_memory_polars` | **~1.7 s** |
| `force_disk_spill` + drilldown + mismatches | `spill_binary` | **~7 s** (was ~12–17 s) |
| `force_disk_spill`, no drilldown | `spill_binary` | **~3 s** |
| Wrong/missing compare columns (silent in-memory failure) | `spill_binary` streaming | **15–100+ s** |

## Critical Finding

`try_in_memory_reconcile` previously failed silently when `compare_columns` referenced columns absent from the file (e.g. benchmark lists 11 columns on an 8-column file), forcing the **per-row Python spill path** and inflating times to **~16–48 s**. Fixed via `filter_compare_columns()`.

## Recommendations

1. Always resolve compare columns from schema before pipeline entry (service already does).
2. For files under 256 MiB, rely on auto in-memory path; avoid `force_disk_spill` in production unless RAM constrained.
3. Disable column drilldown on spill for bulk mismatch reporting when per-column samples are not required.
4. Next major win: **columnar partition spill** (batch-encode per partition, not per-row Python loop).
