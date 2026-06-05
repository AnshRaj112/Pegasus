# Top 20 Bottlenecks (Performance-First Review)

**Method:** cProfile on 10K `||` spill path + wall-clock decomposition on 100K after fixes.  
**Profile host:** Linux, Polars 1.40.1, 4+ cores.

## Top 20 Slowest Functions (cumulative wall)

| Rank | Function | Cumtime | Category |
|------|----------|---------|----------|
| 1 | `ThreadPoolExecutor` / `threading.wait` | ~1.1 s | Sync (partition sides) |
| 2 | `polars.LazyFrame.collect` | ~0.7 s | CPU (expressions) |
| 3 | `TabularReconciliationPipeline._run_spill_path` | ~0.86 s | Orchestration |
| 4 | `PartitionWriter.close` / flush | ~0.57 s | Disk write |
| 5 | `reconcile_partition_vectorized` | ~0.25 s | CPU + spill read |
| 6 | `file_delimited._iter_data_rows` | ~0.22 s | **I/O parse (fallback)** |
| 7 | `load_multichar_csv_fast` / `read_bytes` | ~0.12 s | I/O |
| 8 | `encode_arrow_partition` / Series IPC | ~0.15 s | Serialize |
| 9 | `partition_by` spill groups | ~0.20 s | CPU |
| 10 | `try_in_memory_reconcile` joins | ~0.18 s | CPU |
| 11 | `flat_file_to_polars` (legacy) | ~0.67 s/100K | **Removed from hot path** |
| 12 | `resolve_delimiter_for_paths` | &lt;0.001 s | — |
| 13 | `ProcessPoolExecutor` (if enabled) | variable | **Avoided &lt;64 parts** |
| 14 | `DrilldownCache.register_side` concat | ~0.1 s | RAM |
| 15 | `iter_rows` sample build | ~0.05 s | Python loop |
| 16 | `write_validation_results` | ~0.2 s | Disk (artifacts) |
| 17 | `job_worker._write_json` status | ~0.05–2 s | Disk + poll |
| 18 | `subprocess.Popen` worker | 1–3 s | Process spawn |
| 19 | `gcs_stream` download | cloud-bound | Network |
| 20 | `content_digest` / Merkle precheck | ~0.1–2 s | Optional read |

## Top 20 Most Frequently Called (hot spill 10K)

| Rank | Function | Calls | Note |
|------|----------|-------|------|
| 1 | Polars expr internals | 450K+ | Vectorized; OK |
| 2 | `split_line` / field parse | 20K+ | **Avoid via fast loader** |
| 3 | `StageTimer.__exit__` | 10K+ | Consider sampling |
| 4 | `partition_by` group iterations | ~16–64 | Scales with partitions |
| 5 | `encode_record` (legacy) | 0 | Disabled |

## Top 20 Allocation-Heavy

| Rank | Site | Mitigation |
|------|------|------------|
| 1 | `list[dict]` per row streaming | Delete path for production |
| 2 | `to_list()` per spill partition | Series→Arrow IPC |
| 3 | `pl.DataFrame(chunk)` from dicts | Use multichar fast load |
| 4 | `DrilldownCache.values_for_keys` dict build | Keep key cap ≤1000 |
| 5 | Pandas via clevercsv | Bypassed |

## Top 20 I/O-Heavy

| Rank | Operation | Mitigation |
|------|-----------|------------|
| 1 | Full file read ×2 | Parallel threads; fast parser |
| 2 | Spill `part_*.bin` write/read | in-memory under 256 MiB |
| 3 | GCS download | Prefetch + digest short-circuit |
| 4 | `status.json` rewrite | Throttle callbacks |
| 5 | `VALIDATION_RESULTS.md` | Optional skip |

## Priority Order (implemented)

1. Fix in-memory gate for `||` delimiters — **done**
2. Fast multichar loader — **done**
3. Arrow spill from Series — **done**
4. Row-aware partition cap — **done**
5. Raise process-pool threshold — **done**
