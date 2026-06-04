# GCS Analysis

**Date:** 2026-06-04

## Summary

**GCS is not the bottleneck when objects are prefetched once.** With `prefetch_gcs_delimited_pair` and in-memory reconcile, mocked GCS validation of 100K `||` rows completes in **~1.67 s** with exactly **2 full-object downloads** — matching local SSD performance.

## Implementation Trace

| Step | Module | Behavior |
|------|--------|----------|
| Prefetch | `gcs_delimited.prefetch_gcs_delimited_pair` | Downloads each object once if combined size ≤ `validation_auto_in_memory_max_bytes` |
| Cache | `GcsDelimitedAdapter.cached_object_bytes()` | Serves bytes from RAM |
| Load | `in_memory._load_gcs_delimited_frame` | PyArrow (single-byte delim) or `flat_file` parse |
| Spill (large files) | `try_partition_side_polars` | Uses cache when available; **no PyArrow** for multi-char delim without cache |

## Measured (mocked GCS, 100K 8-col)

| Metric | Value |
|--------|-------|
| Downloads | 2 (source + target) |
| Wall time | 1.67 s |
| Path | `in_memory_polars` |
| Network wait (instrumented) | 0 s post-cache |

## When GCS becomes the bottleneck

| Condition | Effect |
|-----------|--------|
| No prefetch / cache miss | Every read path may call `read_gcs_object_bytes` |
| Combined size &gt; 256 MiB | Streaming spill; multiple prefix reads if not cached |
| Repeated validation without cache inheritance | Re-download |
| High latency + small chunk reads | Not used in current hot path (full-object download preferred) |

## Configuration

- `validation_auto_in_memory_max_bytes` — max combined size for full download + in-memory path
- `GcsDelimitedAdapter.ensure_object_cached()` — explicit cache before pipeline

## Recommendations

1. **Always call** `prefetch_gcs_delimited_pair` before `TabularReconciliationPipeline.run` (service does).
2. Keep combined 100K×8-col datasets under 256 MiB for auto in-memory (current default).
3. For 100GB jobs: use partitioned objects + regional colocation; expect network-bound phase — not measured in this audit.
4. Instrument `network_transfer_seconds` in adapters (currently 0; add around `read_gcs_object_bytes`).

## Proof command

```bash
PYTHONPATH=pegasus-backend/src pytest pegasus-backend/tests/test_gcs_100k_performance.py -q
```
