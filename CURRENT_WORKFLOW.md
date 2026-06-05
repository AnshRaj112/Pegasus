# Current Workflow (Phase 4 — Implemented)

**Date:** 2026-06-04  
**Scope:** `pegasus-backend` Category-1 tabular reconciliation

## Execution Path

```
Source (local | GCS)
  → Streaming Reader (GcsStreamSession | PyArrow CSV | flat_file fallback)
  → RecordBatch / Polars chunk (column projection)
  → Canonicalization (vectorized Polars)
  → Fingerprint (8-byte hash / uint64)
  → Partition (hash bucket)
  → Columnar Spill (ARW1 Arrow IPC — key + fingerprint only)
  → Reconciliation (Polars anti/inner join per partition; optional ProcessPool)
  → Drilldown On Demand (batch values_for_keys for changed keys)
  → Report
```

## GCS (streaming-only)

| Step | Behavior |
|------|----------|
| Prefetch | `warm_metadata()` only — size, CRC32C, MD5 |
| Read | `GcsStreamSession.open_binary()` — chunked read-ahead, reused client |
| Parse | PyArrow `open_csv` on stream, or `TextIOWrapper` + line split |
| Forbidden | `download_as_bytes`, full-object cache, `_cached_full` |

## Copies & Materializations (hot path)

| Stage | Bounded? |
|-------|----------|
| GCS body | Streamed chunks only |
| Parse (spill) | Per-batch DataFrame when file ≥ `streaming_spill_min_bytes` |
| Parse (small) | Full projected DataFrame in RAM |
| Spill write | Arrow IPC blocks appended per partition |
| Reconcile | One partition frame at a time (Polars) |
| Drilldown | Dict built only for changed keys (≤ sample limit) |

## Serialization

| Format | When |
|--------|------|
| **ARW1** Arrow IPC | Default (`use_arrow_ipc_spill`, no payload) |
| **CBL2** | Eager drilldown payload in spill (legacy fallback) |
| Per-row `encode_record` | Disabled in default config |

## Path Selection

| Path | Trigger |
|------|---------|
| `in_memory_polars` | Combined size ≤ `auto_in_memory_max_bytes` |
| `spill_arrow_ipc` | Disk spill + fingerprint-only |
| `spill_binary_lazy_drilldown` | Lazy drilldown + Polars load |
| `_partition_side_streaming` | Multi-char delimiter / Polars load failure |

## Disk I/O

- Write: `PartitionWriter` → `part_NNNNN.bin` (ARW1 blocks)  
- Read: `read_arrow_partition` → Polars join  
- Parallel reconcile: `ProcessPoolExecutor` when partitions ≥ workers  
