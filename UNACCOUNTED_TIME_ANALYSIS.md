# Unaccounted Time Analysis

## Executive summary

A GCS validation job reported **Pipeline Total = 8.18 s** but **worker validation completed in 28.50 s**, leaving **~20.3 s unaccounted** in pipeline stage metrics. Root cause: wall time was only measured inside the spill-path reconciliation loop (`TabularReconciliationPipeline.run()` after `t0 = time.perf_counter()`). The worker timer (`job_worker.py`, `time.time()` from process start) includes **two full-object GCS reads** from abandoned in-memory fast-path attempts that ran **before** the spill timer started.

**Largest unprofiled bottleneck:** duplicate **In-Memory Fast Path** + **Polars Direct Fast Path** attempts on GCS inputs (auto-triggered when `source_bytes + target_bytes ≤ validation_auto_in_memory_max_bytes`, default 256 MiB).

**Fix applied:** When `validation_gcs_streaming_only=true` (default) and either side is `GcsDelimitedAdapter`, skip auto in-memory attempts unless `validation_enable_in_memory_reconcile=true`. Full lifecycle instrumentation now covers HTTP → response.

---

## Observed run (Docker, job `b062f67d-f12c-432b-9a06-c06ab0c08088`)

| Metric | Value |
|--------|-------|
| Worker `validation completed` | **28.50 s** |
| Pipeline `Total` (logged) | **8.18 s** |
| Gap | **~20.32 s** |
| Source rows / target rows | 1 / 9,999 |
| Mismatches exported | 10,000 (NDJSON) |

### Pipeline stages (profiled only)

| Stage | Wall | CPU | Bytes read | Bytes written |
|-------|------|-----|------------|---------------|
| Read Source | 3.31 s | 0.04 s | 1,076,691 | 0 |
| Partition Source | 1.05 s | 0.75 s | 0 | 432 |
| Read Target | 3.57 s | 0.04 s | 1,435,788 | 0 |
| Partition Target | 4.48 s | 1.06 s | 0 | 219,978 |
| Reconciliation | 0.11 s | 0.09 s | 220,410 | 0 |
| Report | 0.0004 s | 0.0004 s | 0 | 0 |
| **Pipeline Total** | **8.18 s** | **2.01 s** | **2,732,889** | **220,410** |

Read/partition wall times overlap across two partition threads; **Total** is end-to-end inside the spill path only.

---

## Two clocks (why metrics disagreed)

| Clock | Where | Starts | Stops | What it includes |
|-------|--------|--------|-------|------------------|
| **Worker total** | `job_worker.py` | Worker process: status `running` | After `result.json` | Settings, GCS prefetch, schema, **in-memory attempts**, spill pipeline, mismatch NDJSON, result write |
| **Pipeline total** | `pipeline.py` | `t0 = perf_counter()` immediately before spill partition | After reconciliation | Spill partition + reconcile only |

`ValidationService` used `time.perf_counter() - t0` around `pipeline.run()` only — same blind spot as pipeline `Total`.

---

## Reconstructed timeline (100% of ~28.5 s worker wall)

Epoch anchors from terminal: pipeline ended **10:22:19.656**; worker logged completion **10:22:19.668** → worker started **~10:21:51.17**.

| Phase | Stage | Est. wall | CPU (est.) | Bytes read | Bytes written | Previously profiled? |
|-------|--------|-----------|------------|------------|---------------|----------------------|
| 1 | HTTP Request Start → Job Creation | ~0.05 s | low | 0 | meta.json | **No** → now yes |
| 2 | Queue Wait | ~0–2 s | 0 | 0 | 0 | **No** → now yes |
| 3 | Worker Init (settings, logging) | ~0.5 s | low | 0 | status.json | **No** → now yes |
| 4 | GCS Prefetch (metadata) | ~0.5 s | low | 0 | 0 | **No** → now yes |
| 5 | Schema And Planning (`get_schema` ×2) | ~1 s | low | ~header prefixes | 0 | **No** → now yes |
| 6 | **In-Memory Fast Path** (full GCS read ×2) | **~10 s** | moderate | ~2.5 MiB ×2 | 0 | **No** — **root cause** |
| 7 | **Polars Direct Fast Path** (retry full read ×2) | **~10 s** | moderate | ~2.5 MiB ×2 | 0 | **No** — **root cause** |
| 8 | Pipeline spill (Read/Partition/Reconcile) | **8.18 s** | 2.01 s | 2.73 MiB | 220 KiB | **Yes** |
| 9 | Report Generation | ~0.001 s | ~0 | 0 | VALIDATION_RESULTS.md | Partial |
| 10 | Mismatch Export (1000 rows NDJSON) | ~0.01 s | low | 0 | mismatches.ndjson | **No** → now yes |
| 11 | Result Serialization | ~0.01 s | low | 0 | result.json | **No** → now yes |
| 12 | Job Finalization (status completed) | ~0.01 s | low | 0 | status.json | **No** → now yes |
| 13 | HTTP poll → Response (first completed GET) | ~0.05 s | low | result.json | JSON payload | **No** → now yes |
| | **Worker Total** | **~28.5 s** | | | | |

Stages 6–7 explain **~20 s** not present in Pipeline Total. Each calls `try_in_memory_reconcile` → `_load_gcs_delimited_frame` → `session.open_binary()` + PyArrow full parse. Attempts return `None` (e.g. exception or failed join path) but **still consume network and CPU**. Stage 8 then **re-reads** both objects for streaming spill.

---

## Code path (before fix)

```
job_worker (start = time.time())
  ValidationService._validate_delimited_adapters_sync
    prefetch_gcs_delimited_pair          # metadata only
    source.get_schema()                  # header prefix from GCS
    pipeline.run():
      get_schema()                       # again
      try_identical_precheck             # fast, metadata
      if combined ≤ 256 MiB:             # auto_in_memory_max_bytes
        try_in_memory_reconcile()        # FULL GCS download #1 (both sides)
      if combined ≤ polars_spill_max:
        try_in_memory_reconcile()        # FULL GCS download #2 (polars_direct)
      t0 = perf_counter()                # ← Pipeline Total starts here
      parallel partition + reconcile       # 8.18 s
    write_validation_results
    pipeline_result_to_run_result        # builds Polars mismatch frame
  _resolve_job_mismatch_artifact         # write_ndjson 1000 rows
```

`validation_enable_in_memory_reconcile` defaults to **false**, but `should_try_in_memory_reconcile()` still returns **true** when combined size ≤ `validation_auto_in_memory_max_bytes` (256 MiB). GCS objects (~1.0 MiB + ~1.4 MiB) always triggered both attempts.

---

## Other audited areas (not the 20 s gap)

| Area | Finding |
|------|---------|
| Polling loops | Frontend polls `GET /validate/jobs/{id}` every ~1 s; **does not** extend worker CPU. Drain loop `_reap_finished` polls subprocess every ≤2 s. |
| Queue wait | Included in worker epoch gap when job is queued; typically sub-second for single job. |
| Worker sync | `ThreadPoolExecutor(2)` for source/target partition **inside** profiled 8.18 s. |
| Thread/process waits | Subprocess spawn overhead &lt; 1 s; not 20 s. |
| Report uploads | No GCS upload in worker (`upload_seconds: 0`). |
| Mismatch export | ~10 ms for 1000-row NDJSON at end of run. |
| Database writes | On **first completed poll** via `maybe_persist_completed_job`; not in worker 28.5 s unless persistence enabled. |
| GCS uploads | N/A for validate/local cloud path. |

---

## Fix and instrumentation (implemented)

### 1. Skip redundant GCS in-memory attempts

- `TabularPipelineConfig.gcs_streaming_only` wired from `validation_gcs_streaming_only`.
- `_should_attempt_in_memory()` returns false for GCS auto-path when streaming-only unless explicit `enable_in_memory_reconcile`.

### 2. Full lifecycle profiler

Module: `pegasus.validation.lifecycle_profiler`

Artifacts per job:

- `lifecycle_timings.json`
- `lifecycle_report.md`
- `result.json` → `lifecycle` summary

Stages instrumented:

HTTP Request Start → Job Creation → Queue Wait → Worker Init → Validation Start → GCS Prefetch → Schema And Planning → Pipeline Precheck → In-Memory Fast Path → Polars Direct Fast Path → Read Source → Partition Source → Read Target → Partition Target → Reconciliation → Mismatch Export → Report Generation → Pipeline Total → Result Serialization → Database Updates → GCS Uploads → Job Finalization → HTTP Response.

Each stage records: **wall time, CPU time, bytes read, bytes written**.

---

## Expected outcome after fix

For the same GCS ~2.5 MiB pair workload:

| Metric | Before | After (expected) |
|--------|--------|------------------|
| Worker total | ~28.5 s | **~9–10 s** |
| Pipeline Total | 8.18 s | ~8.18 s (unchanged) |
| Unaccounted vs pipeline | ~20.3 s | **~1–2 s** (init, prefetch, export, serialization) |

### Follow-up (100K `||` / 4 columns)

| Issue | Fix |
|-------|-----|
| `source_rows=1` / `mismatches=0` vs manifest 8000 | Disabled bogus **Merkle spill precheck** when spill bytes ≪ input bytes; validate column names on parse |
| ~23 s worker for ~8 MiB | Skip auto in-memory for **multi-char delimiters** (`||`); stream chunks instead of 2× full load + spill |
| `generated-10m/manifest.json` misleading | Added `column_count: 4`, `columns: [id, sku, amount, region]`, note that 10M ≠ 100K |

Local `generated-100k` after fix: **~4.8 s**, 100000/104000 rows, 8000 mismatches.

Parsing/CSV optimizations were **not** changed; only removal of duplicate full-object reads before spill.

---

## How to verify

1. Re-run the same GCS validation job.
2. Inspect `lifecycle_timings.json` under the job directory.
3. Confirm `In-Memory Fast Path` and `Polars Direct Fast Path` are **0 s** or absent.
4. Confirm `Worker Total` ≈ `Pipeline Total` + small overhead.
5. Compare `validation completed in X.XXs` log line to `Pipeline Total`.

```bash
# Example (job dir on host or in container)
cat /tmp/pegasus_validation_jobs/<job_id>/lifecycle_report.md
```

---

## Tests

- `tests/test_gcs_skip_in_memory_fast_path.py` — GCS + streaming-only skips auto in-memory
- `tests/test_lifecycle_profiler.py` — lifecycle artifacts and pipeline stage ingest
