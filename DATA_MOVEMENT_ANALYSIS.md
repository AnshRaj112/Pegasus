# Data Movement Analysis

**Goal:** Minimize bytes read, written, copied, serialized, and deserialized.

## Per-Stage Estimates (100K rows, 8 compare cols, ~21 MiB combined)

| Stage | Bytes Read | Bytes Written | Bytes Copied | Serialized | Deserialized |
|-------|------------|---------------|--------------|------------|--------------|
| GCS (cached) | 21 MiB download | — | 21 MiB → adapter cache | — | — |
| GCS (streaming) | 21 MiB stream | — | Chunk buffers only | — | — |
| Parse (projected) | 21 MiB file | — | ~8 cols → frame (~15 MiB) | — | Arrow→Polars |
| Canonicalize | — | — | In-place Polars | — | — |
| Fingerprint | — | — | 8 bytes/row | — | — |
| Spill (CBL2 legacy) | — | ~12–18 MiB spill | DataFrame→lists→bytes | ~12 MiB | — |
| Spill (ARW1) | — | ~6–8 MiB spill | Arrow IPC only | ~6 MiB | — |
| Reconcile (dict legacy) | spill read 2× | — | 2× partition into dict | decode all keys | — |
| Reconcile (Polars) | spill read 2× | — | 2× Arrow→Polars | minimal | Arrow decode |
| Drilldown (eager spill) | — | payload in spill | per-row CB01 | embedded | full partition |
| Drilldown (lazy) | — | 0 spill payload | frame retained | 0 | keys × mismatch count |

## Phase 4 Reductions

1. **~50% spill write reduction** — fingerprint-only ARW1 vs CBL2+payload  
2. **~90% drilldown deserialize reduction** — batch lookup for ≤1000 changed keys vs full partition payload decode  
3. **Column projection** — wide files: read `(identity + compare)` columns only, not 1000 columns  
4. **GCS streaming** — eliminates duplicate local copy when `validation_gcs_streaming_only=true`  

## 80 GB + 80 GB / 10 GB RAM (target)

| Component | Bound |
|-----------|-------|
| In-memory structures | O(chunk_rows × cols × workers) |
| Spill per partition | O(partition_rows × (key + 8)) |
| Drilldown cache | O(dataset) if full frame retained — **mitigation:** partition-scoped frames or re-stream on mismatch |
| Reconcile | O(partition_rows) Polars frames, not Python dict per key |

**Next step for 80 GB:** Polars `scan_csv` lazy spill (Phase 5) + partition worker processes.
