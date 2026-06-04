# Flamegraph Report

**Date:** 2026-06-04  
**Profile source:** `docs/benchmarks/profile-stats.pstats`  
**Text stats:** `docs/benchmarks/profile-stats.txt`

## Note on flamegraph generation

`flameprof` was not available in the environment. Use:

```bash
pip install flameprof
flameprof docs/benchmarks/profile-stats.pstats > docs/benchmarks/flame.svg
```

Or SnakeViz: `snakeviz docs/benchmarks/profile-stats.pstats`

## Top CPU Consumers (cProfile `tottime`)

From spill+drill profile on 100K 8-col (`profile_pipeline.py --force-spill`):

| Rank | Function | Self time share |
|------|----------|-----------------|
| 1 | `_write_frame_partitions` inner loop | Serialization |
| 2 | `encode_record` / `encode_compare_payload_values` | Binary spill |
| 3 | `_load_frame` / `_flat_parse_to_polars` | Multi-char parse |
| 4 | `iter_partition` / `decode_record` | Reconcile read |
| 5 | Polars `partition_by` | Grouping |

When streaming fallback is triggered (historical worst case):

| Rank | Function | Impact |
|------|----------|--------|
| 1 | `row_fingerprint_bytes` | 67 s cumulative / 100K rows |
| 2 | `PartitionWriter.write` | 53 s |
| 3 | `encode_compare_payload` | 20 s |
| 4 | `canonical` | 3.9M calls |
| 5 | `csv.reader` | Row iteration |

## Top Memory Consumers (inferred)

| Consumer | Path |
|----------|------|
| Full `pl.DataFrame` × 2 | In-memory |
| Per-partition `dict[str, tuple]` | Spill reconcile + drilldown |
| `bytearray` spill buffers | PartitionWriter |

## Top Allocation Sources

| Source | Type |
|--------|------|
| `batch_to_dicts` | `dict` per row |
| `encode_compare_payload` dict (fixed) | `list[str]` per row |
| `canonical()` | Temporary strings |
| Polars materialize | Columnar (lower churn) |

## Interpretation

The flame profile shape is **bimodal**:

1. **Healthy path:** wide plateau on Polars I/O + moderate `encode_record` spine.
2. **Degraded path:** deep stack under `row_fingerprint_bytes` and `csv.reader` — indicates path selection bug or forced streaming.

See `TOP_50_FUNCTIONS.md` for the full sorted table.
