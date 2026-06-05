# Architecture Diff (Baseline → Phase 4)

| Area | Before | After |
|------|--------|-------|
| GCS ingest | Full download if size ≤ 256 MiB | Streaming default option; prefetch gated by `validation_gcs_streaming_only` |
| Parse | Full DataFrame or per-row dicts | Projected columns via PyArrow `include_columns` |
| Spill format | CBL2 / per-row CB01 | **ARW1** Arrow IPC blocks (identity + 8-byte fingerprint) |
| Spill payload | Optional column-major payload on disk | **Fingerprint-only** (`fingerprint_only_spill`); payloads not spilled |
| Reconcile | Python `dict` per partition | **Polars join** on spilled Arrow frames |
| Drilldown | Full-side dict at register time | **Batch** `values_for_keys` for changed keys only |
| Serialization | Python lists → CBL2 encode | Arrow `RecordBatch` → IPC stream |
| Deserialize | `iter_partition` → dicts | `pl.from_arrow` via `read_arrow_partition` |
| Legacy JSON spill | Supported in decode | Removed from hot path (CB01 still decoded if present) |

## New Modules

- `pegasus/validation/pipeline/arrow_spill.py` — ARW1 encode/decode  
- `pegasus/validation/pipeline/partition_reconcile.py` — vectorized per-partition reconcile  

## Modified Modules

- `pipeline.py` — delegates reconcile to `partition_reconcile`  
- `polars_spill.py` — Arrow IPC write path, column projection on read  
- `drilldown_cache.py` — batch key lookup  
- `config.py` — `use_arrow_ipc_spill`, `fingerprint_only_spill`  
- `pyarrow_io.py` — `include_columns` projection  
- `validation_service.py` — GCS streaming flag, pipeline config defaults  

## Removed / Deprecated Hot-Path Patterns

- Per-partition `src_fp_map` / `src_payload_map` Python dict reconcile loop in `pipeline.py`  
- Eager spill payload when lazy drilldown + fingerprint-only enabled  
