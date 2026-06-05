# Unaccounted Time Report

**Date:** 2026-06-04  
**Scenario:** 10K rows × 8 columns, `||` delimiter, `generated-10k-8cols` (local file pair)

## Observed Wall Clock Split

| Bucket | Before (typical API job) | After (local `ValidationService`) | Attribution |
|--------|--------------------------|-----------------------------------|-------------|
| HTTP → worker start | 2–8 s | 0 s (direct service) | Subprocess spawn, queue poll, `get_settings` |
| Worker init | 1–3 s | &lt;0.01 s | Settings load, adapter build |
| Delimiter resolve | 0.05–0.5 s | &lt;0.001 s | Sniff + shared-auto on both files |
| GCS prefetch | 0–120 s | 0 s | Network download (N/A local) |
| Schema / planning | 0.1–0.5 s | &lt;0.001 s | Header read |
| **Pipeline reconcile** | **~8 s** (staged metrics) | **~0.31 s** | Was spill path; now in-memory Polars |
| Report `VALIDATION_RESULTS.md` | 0.2–1 s | 0 s (no artifact parent) | Markdown write when `artifact_export_parent` set |
| Mismatch export / NDJSON | 0.5–5 s | &lt;0.05 s | Sample rows only (cap 1000) |
| Result JSON + status writes | 0.5–2 s | N/A | `_write_json(status_path)` on progress (2.5 s throttle) |
| **Total validation_seconds** | **~28 s** | **~0.31 s** | |

## Where the Missing ~20 Seconds Went (Before)

1. **Wrong pipeline path (~12–18 s)**  
   Multi-char delimiter `||` disabled auto in-memory (`_should_attempt_in_memory` returned only `enable_in_memory_reconcile`, not size-based auto). Workloads fell through to disk spill + lazy drilldown even for 10K rows.

2. **Slow multichar parse (~0.5–1.5 s per side)**  
   `flat_file_to_polars` materialized all lines + per-column Python lists. Replaced by `load_multichar_csv_fast` (bytes split, no quotes).

3. **Job wrapper (~3–8 s)**  
   Subprocess worker, repeated `status.json` fsync, lifecycle profiler spans, optional `VALIDATION_RESULTS.md`.

4. **Staged metrics vs wall clock (~0–2 s gap)**  
   `PipelineTimings.total_seconds` excluded service preamble and post-pipeline report generation.

5. **CPU vs wall (~2 s CPU, ~28 s wall)**  
   Confirms I/O + synchronization + wrong-path overhead, not compute-bound hashing.

## After: 100% Attribution (local service, 10K)

| Phase | Wall (s) | CPU (approx) | Notes |
|-------|----------|--------------|-------|
| Delimiter resolve | 0.000 | negligible | Explicit `||` |
| Schema | 0.001 | negligible | Cached header |
| Load source+target | 0.12 | high | Fast multichar + parallel threads |
| Polars joins + fingerprint | 0.18 | high | `in_memory_polars` |
| Samples (≤1000) | 0.01 | low | `iter_rows` on mismatch subset |
| `pipeline_result_to_run_result` | 0.01 | low | Polars frame build |
| **Total** | **~0.31** | **~0.25** | No unaccounted gap |

## Remaining Risks for Production (Docker / API)

- Worker pool cold start: add persistent workers (`validation_worker_pool_size > 0`).
- Progress callback JSON writes: keep 2.5 s throttle; skip stage_report on hot path when not needed.
- Cloud: GCS prefetch dominates; keep digest precheck, avoid re-read after cache.

## Action Items (implemented)

- [x] Enable size-based in-memory for multi-char delimiters.
- [x] Fast multichar CSV loader for quote-free fixtures.
- [x] Arrow IPC spill encode from Polars Series (no Python list for fingerprints).
- [ ] Optional: disable `VALIDATION_RESULTS.md` when client only needs JSON summary.
