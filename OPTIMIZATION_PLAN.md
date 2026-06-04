# Optimization Plan

**Date:** 2026-06-04  
**Status:** Phase 1 and Phase 2 implemented

## Completed (this pass)

| Item | Impact |
|------|--------|
| `filter_compare_columns` — prevent silent in-memory fallback | **~16 s → ~1.7 s** when columns misconfigured |
| `encode_compare_payload_values` — avoid per-row dict | Drilldown spill **~12 s → ~7 s** |
| Canonicalize in Polars before spill payload | Cuts duplicate `canonical()` in encode |
| Fused `_canonical_parts` in streaming fallback | ~2× on Python spill when triggered |
| `partition_id` via xxhash64 | Minor per-row savings |

## Phase 2 — Completed

| Item | Result |
|------|--------|
| **P0 Columnar spill (CBL2)** | `encode_columnar_partition` + multi-block `iter_partition`; serialization **~4 s → ~0.5 s** |
| **P1 clevercsv ingest** | `clevercsv_io.py` tried before `flat_file` fallback |
| **P2 Lazy drilldown** | `DrilldownCache` + fingerprint-only spill; path `spill_binary_lazy_drilldown` |
| **P3 Instrumentation** | GCS `network_transfer_seconds`; `pipeline_metadata` includes `path` + `timings` |

**100K mismatch spill+drill:** ~12 s → ~7 s (Phase 1) → **~4.6–6 s** (Phase 2, median ~5 s).

Config flags: `lazy_column_drilldown` (default True), `use_columnar_spill` (default True).

## Phase 3 — Scale-out

| Item | Target |
|------|--------|
| Partition worker processes | Linear scaling with cores |
| Larger-than-RAM streaming | Polars `scan_csv` + lazy spill (no full parse) |
| 1000+ column projection | Column subset early; avoid materializing full rows |

## Target alignment

| Goal | Status |
|------|--------|
| 100K rows/s narrow | **Met** on in-memory path (~59–139K) |
| 50K rows/s wide | Not validated |
| 100 GB / 10 min | Requires distributed + columnar I/O (not met) |

## Backward compatibility

Performance changes intentionally favor speed over legacy JSON spill. Old spill files are not migrated — jobs use ephemeral workspaces.
