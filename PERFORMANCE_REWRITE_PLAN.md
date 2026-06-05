# Performance Rewrite Plan

**Status:** Phase 1 implemented (2026-06-04)

## Root Cause

Multi-character delimiters (`||`, emoji, `xx`) **disabled** the auto in-memory fast path. Workloads spilled to disk, parsed rows as Python dicts, and spent wall time on I/O synchronization—not CPU.

## Phase 1 — Implemented

| # | Change | Files | Impact |
|---|--------|-------|--------|
| 1 | Size-based in-memory for multi-char delimiters | `pipeline.py` | 10K: 8s → **0.31s** service path |
| 2 | `load_multichar_csv_fast` (bytes split, no quotes) | `readers/multichar_csv.py`, `in_memory.py`, `clevercsv_io.py` | 100K load ~670ms → **~120ms** |
| 3 | Arrow IPC spill from Polars Series | `arrow_spill.py`, `polars_spill.py` | Spill encode avoids Python int lists |
| 4 | Row-aware partition cap (~2K rows/partition) | `pipeline.py` | Less empty-partition overhead |
| 5 | Process pool only if ≥64 partitions | `partition_reconcile.py` | Avoid spawn tax on 10K–100K |

## Phase 2 — Recommended Next

| # | Item | Expected win |
|---|------|--------------|
| 1 | Persistent validation worker pool (default on) | −2–8 s API jobs |
| 2 | mmap `read_arrow_partition` | Spill reconcile −20% large files |
| 3 | Streaming multichar parser (chunked, no full `read_bytes`) | 1M+ rows memory bound |
| 4 | Vectorized drilldown samples (no `iter_rows`) | Mismatch-heavy −10% |
| 5 | Skip `VALIDATION_RESULTS.md` when not requested | −0.2–1 s |
| 6 | Single-pass reconcile without spill for “fits in RAM” even with mismatches | Already in Phase 1 |

## Phase 3 — Delete List

- [ ] `_partition_side_streaming` per-row path — keep only as last-resort with loud metric
- [ ] Legacy per-row `encode_record` spill loop (already raises)
- [ ] Redundant `get_schema()` calls inside pipeline (cache on adapter)

## Targets vs Measured (local, after Phase 1)

| Target | Measured |
|--------|----------|
| 10K &lt; 1 s | **0.31 s** ✓ |
| 100K &lt; 3 s | **1.25–1.41 s** ✓ |
| 1M &lt; 10 s | Not re-run (expect ~12–15 s in-memory if RAM OK) |
| 10M &lt; 60 s | Requires streaming Phase 2 |
| 100GB &lt; 10 min | Requires spill + parallel + cloud prefetch tuning |

## Validation

- `tests/test_multichar_csv_fast.py`
- `tests/test_reconciliation_throughput.py`
- `tests/test_generated_100k_manifest.py`
