# Optimization Plan

**Date:** 2026-06-04  
**Status:** Phase 1 complete (hot-path integration)

## Phase 1 — Completed

- [x] Wire binary spill (`spill.py`) into `pipeline.py`
- [x] Replace SHA256 with `xxhash64` default
- [x] Parallel source/target partitioning (`ThreadPoolExecutor`)
- [x] Polars vectorized spill for PyArrow and multi-char (via frame load)
- [x] Active-partition-only reconcile (`list_partition_ids`)
- [x] Stage timings (`PipelineTimings` → `extra_stats.timings`)
- [x] Compact compare-column payload (`encode_compare_payload`)
- [x] `polars_direct` fast path when disk spill not forced
- [x] Columnar flat-file → Polars conversion
- [x] Benchmark + profile scripts
- [x] Throughput regression tests

## Phase 2 — Near Term (1–2 weeks)

### P1: Multi-char parse acceleration

- Integrate batched CleverCSV / Rust-backed parser for `||` and custom delimiters
- Target: 100 MiB read &lt; 1 s

### P2: Lazy column drilldown

- Spill fingerprint-only; on mismatch, re-read row from source adapter or mmap spill index
- Target: drilldown spill within 2× non-drilldown time

### P3: Bulk spill encode

- Replace per-row `encode_record` loop with columnar block writer (Arrow IPC or custom struct array)
- Target: serialization &lt; 0.2 s / 100K rows

### P4: Reconcile without full partition RAM

- Sort-merge spill files by identity key per partition
- Target: 1 GB files on 8 GiB RAM

### P5: GCS benchmarks + tuning

- Parallel range GET, 8–16 MiB read-ahead, connection pool reuse
- Benchmark local vs GCS in `scripts/benchmark_gcs_reconciliation.py`

### P1b: Precheck (implemented 2026-06-04, fixed regression 2026-06-04)

- [x] Wire `validation_enable_merkle_fast_path` → `precheck.py`
- [x] Digest computed **once** during `ensure_object_cached` (never re-hash in precheck)
- [x] Size mismatch → skip precheck immediately (no hash, no GCS reload)
- [x] GCS metadata from adapter fields (no reload when `size_bytes` already known)
- [x] Fixed prefetch cap: was `max(64MB, 512MB)` → always 512MB; now uses `validation_auto_in_memory_max_bytes` (default **256MB**)
- [x] Spill Merkle capped at 32MB total hashed
- [ ] HLL precheck (`validation_tabular_enable_hll_precheck`) — still unwired

## Phase 3 — Scale (1 GB+)

- Pipeline parallelism: reader → fingerprint → partition → reconcile → report queues
- Sub-partition when bucket &gt; memory threshold
- Merkle tree precheck (`validation_enable_merkle_fast_path`)
- Optional: Rust extension module for spill encode/decode

## Phase 4 — 100 GB

- Distributed partition workers (`PEGASUS_WORKER_INDEX`)
- Object-store native readers (Parquet/ORC)
- Result aggregation without central O(n) memory

## Configuration Recommendations

| Setting | Current | Recommended |
|---------|---------|-------------|
| `validation_auto_in_memory_max_bytes` | 64 MiB | 128–256 MiB if RAM allows |
| `fingerprint_algorithm` | xxhash64 | Keep unless compliance requires SHA256 |
| `enable_column_drilldown` | true | false for bulk equality checks |
| `force_disk_spill` | false | true only for spill testing |

## Success Metrics (Re-check monthly)

| Size | Target | Current (local, `||`) |
|------|--------|------------------------|
| 20 MB | &lt; 1 s | ~0.3–1.4 s |
| 100 MB | &lt; 3 s | ~6–7 s (est.) |
| 1 GB | &lt; 10 s | Not met |
