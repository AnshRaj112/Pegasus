# Target Workflow (Phase 4)

**Date:** 2026-06-04

## Execution Path

```
Source (GCS | Local)
  → Streaming Reader (PyArrow CSV / GCS open_gcs_binary)
  → RecordBatch / Polars chunk (projected columns only)
  → Canonicalization (vectorized Polars expr)
  → Fingerprint (vectorized hash, 8-byte binary)
  → Partition (hash bucket)
  → Columnar Spill (Arrow IPC ARW1 — key + fingerprint only)
  → Vectorized Reconciliation (Polars anti/inner join per partition)
  → Drilldown On Demand (batch lookup for changed keys only)
  → Report
```

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| No full-file local copy | GCS `open_gcs_binary` + PyArrow streaming; optional `validation_gcs_streaming_only` |
| Column projection | `include_columns` in PyArrow `ConvertOptions` |
| Fingerprint-only spill | `fingerprint_only_spill=True`; payloads not written to disk |
| Columnar spill | `arrow_spill.encode_arrow_partition` (IPC stream) |
| Vectorized reconcile | `partition_reconcile.reconcile_partition_vectorized` |
| Lazy drilldown | `DrilldownCache.values_for_keys` — dict built only for mismatch keys |
| Bounded memory | Spill + chunk size + partition count; no O(dataset) reconcile dict |

## GCS

- **Eliminated:** `download_as_bytes`, `read_gcs_object_bytes`, `_cached_full`, `ensure_object_cached`  
- **Implemented:** `GcsStreamSession` — cached storage client, chunked read-ahead, PyArrow CSV on `blob.open("rb")`  
- **Prefetch:** metadata only (`warm_metadata`); no object body download  
- **Precheck digest:** GCS MD5/CRC32C metadata (not full-file xxhash)  
- **Browse UI:** chunked `blob.open` → local file (export only; not used by validation pipeline)  

## Distributed (Kubernetes-ready)

- Partition files are independent (`part_{pid:05d}.bin`)  
- Workers reconcile one `pid` without cross-partition state  
- Checkpoint = partition file presence + Merkle digest precheck  

## Performance Targets

| Dataset | Target |
|---------|--------|
| 100K rows | < 1 s (in-memory), < 3 s (spill + drilldown) |
| 1M rows | < 5 s |
| 10M rows | < 60 s |
| 1000 columns (20 compared) | Project 22 columns only |
| 80 GB + 80 GB / 10 GB RAM | Streaming spill + partition workers (scale-out) |
