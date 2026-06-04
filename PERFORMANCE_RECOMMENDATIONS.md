# Performance Recommendations

**Date:** 2026-06-03  
**Status:** Partially implemented — see OPTIMIZATION_PLAN.md for roadmap

---

## Implemented (This Audit)

### 1. Replace SHA256 with xxHash64 as Default Fingerprint

**Rationale:** Micro-benchmark shows xxHash64 is **16× faster** (1.41M vs 862K hashes/s) with acceptable collision resistance for reconciliation (birthday bound ~4 billion records).

**Implementation:** `pegasus/validation/pipeline/fingerprint.py`  
**Config:** `validation_tabular_fingerprint_algorithm=xxhash64`

### 2. Binary Partition Spill Format (PGS2 v1)

**Rationale:** Eliminates `json.dumps`/`json.loads` from hot path. Reduces spill record size by ~60% for no-drilldown case.

**Format:**
```
[4-byte BE length][2-byte BE key_len][key UTF-8][8-byte fingerprint][optional: 4-byte payload_len + orjson payload]
```

**Implementation:** `pegasus/validation/pipeline/spill.py`

### 3. Buffered Partition Writes

**Rationale:** Amortize syscall cost. Default 256 KiB flush threshold.

**Config:** `validation_tabular_spill_flush_bytes=262144`

### 4. Parallel Source/Target Partitioning

**Rationale:** Source and target are independent; parallelizing saves ~40% wall time on partition stage.

**Implementation:** `ThreadPoolExecutor(max_workers=2)` in `pipeline.py`

### 5. Compare-Column-Only Drilldown Payloads

**Rationale:** Column drilldown with full row JSON was 4.5× slower than hash-only spill. Storing only canonicalized compare columns reduces payload ~90%.

### 6. Polars Vectorized Spill Path

**Rationale:** For single-byte delimiters, compute identity/fingerprint/partition in Polars/Rust instead of Python dict loop.

**Implementation:** `pegasus/validation/pipeline/polars_spill.py`  
**Throughput:** 100K rows in 10.5 s (vs 29.3 s pre-optimization)

### 7. Adaptive Partition Bucket Count

**Rationale:** Avoid scanning 2048 empty partitions for small files.

| File Size | Buckets |
|-----------|---------|
| ≤ 4 MiB | 16 |
| ≤ 32 MiB | 64 |
| ≤ 128 MiB | 256 |

### 8. Stage Timing Instrumentation

**Rationale:** Enables ongoing profiling via `result.extra_stats["timings"]`.

**Implementation:** `pegasus/validation/pipeline/timing.py`

---

## Recommended — High Priority

### R1. Lazy Column Drilldown

**Problem:** Drilldown payloads written for every row even when files match.  
**Recommendation:** Spill hash-only by default; re-read source/target rows only for changed keys during reconcile.  
**Expected gain:** 3–5× on drilldown-enabled runs with few mismatches.

### R2. Stream-First Reconciliation

**Problem:** Both sides written to disk then read back — double I/O.  
**Recommendation:** Build source partition index in memory (or mmap) while streaming target, reconciling per-partition inline.  
**Expected gain:** Eliminate disk read phase (~40% of spill time).

### R3. Extend Polars Spill to GCS and Multi-Char Delimiters

**Problem:** Polars spill only works for `FileDelimitedAdapter` with single-byte delimiters.  
**Recommendation:** Use CleverCSV batched parsing or pre-normalize multi-char delimiters to PyArrow-compatible form.  
**Expected gain:** 5–10× on multi-char delimiter workloads.

### R4. Wire Merkle Fast Path

**Problem:** `validation_enable_merkle_fast_path=true` but not connected to pipeline.  
**Recommendation:** Compute rolling partition checksums during spill; skip reconcile when all partitions match.  
**Expected gain:** Near-O(partitions) for identical files regardless of row count.

### R5. mmap Partition Reads

**Problem:** Sequential `read()` + decode per record during reconciliation.  
**Recommendation:** Memory-map partition files; bulk-decode with numpy structured arrays.  
**Expected gain:** 2–3× on disk read phase.

---

## Recommended — Medium Priority

### R6. Adaptive Hot-Partition Splitting

**Problem:** Skewed keys create partitions exceeding memory budget.  
**Recommendation:** Monitor partition byte size during spill; sub-partition when threshold exceeded.  
**Config candidate:** `validation_tabular_max_partition_bytes`

### R7. Column Index Row Representation

**Problem:** Adapter contract yields `dict[str, Any]` per row — repeated column name hashing.  
**Recommendation:** Internal `RowBatch` with column index arrays; convert to dict only at API boundary.  
**Expected gain:** 20–30% on Python loop paths.

### R8. Apache Arrow IPC for Spill

**Problem:** Custom binary format requires hand-rolled encode/decode.  
**Recommendation:** Arrow RecordBatch streams per partition — zero-copy reads, ecosystem tooling.  
**Trade-off:** Larger files for small payloads; better for wide datasets.

### R9. GCS Parallel Range Reads

**Problem:** Single-stream GCS reads underutilize bandwidth.  
**Recommendation:** Chunk object into parallel range requests with read-ahead buffer.  
**Expected gain:** 2–4× on GCS-bound workloads.

### R10. Process Pool for Large Jobs

**Problem:** GIL limits Python loop throughput even with threads.  
**Recommendation:** Enable `validation_worker_pool_size > 0` with partition-level worker dispatch (reference engine pattern in `reference/category1_engine/`).  
**Expected gain:** Linear scaling with CPU cores for spill path.

---

## Recommended — Low Priority

### R11. MessagePack for Drilldown Payloads

Currently using orjson (already fast). MessagePack offers marginal gains over orjson for small dicts.

### R12. CRC64 / MurmurHash3 Alternatives

xxHash64 wins micro-benchmarks. No change recommended unless cryptographic guarantees required (use SHA256 via config).

### R13. Connection Pooling for GCS

Reuse `storage.Client` across requests within a worker process.

### R14. Eliminate PyArrow → Polars → Dicts Chain

Stay in Arrow batches through partition stage; compute hashes via Arrow compute functions.

---

## Configuration Tuning Guide

| Setting | Default | Recommendation |
|---------|---------|----------------|
| `validation_auto_in_memory_max_bytes` | 64 MiB | Increase to 128–256 MiB if RAM available |
| `validation_tabular_fingerprint_algorithm` | xxhash64 | Keep default |
| `validation_tabular_enable_column_drilldown` | true | Set false for count-only validation |
| `validation_tabular_spill_flush_bytes` | 256 KiB | Increase to 1–4 MiB on SSD |
| `validation_tabular_partition_preset` | medium | Use `small` for < 1M rows |
| `validation_reconciliation_chunk_rows` | 500K | Keep for spill; auto-tuned by workload budget |

---

## Anti-Patterns to Avoid

1. **Do not use SHA256 for row fingerprints** unless cryptographic collision resistance is required
2. **Do not store full row dicts** in spill files when only compare columns are needed
3. **Do not use JSON** in partition spill hot paths
4. **Do not iterate 8192 partition slots** when adaptive bucketing yields 16
5. **Do not disable in-memory auto-path** for files ≤ 64 MiB without reason
6. **Do not use column drilldown** for high-throughput count-only runs

---

## Monitoring

Export these metrics from `PipelineResult.extra_stats`:

```json
{
  "timings": { "fingerprint_generation_seconds": 0.0, "..." },
  "fingerprint_algorithm": "xxhash64",
  "spill_format": "binary_v1",
  "polars_spill": true,
  "num_partitions": 64
}
```

Alert thresholds:
- `rows_per_second < 10,000` for datasets < 100 MiB → investigate path selection
- `disk_read_seconds / total_seconds > 0.5` → consider stream-first reconcile
- `serialization_seconds / total_seconds > 0.5` → verify Polars spill activation
