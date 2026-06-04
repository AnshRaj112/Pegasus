# Performance Profile

**Date:** 2026-06-04  
**Host:** DM1007 (4 CPU cores)  
**Dataset:** `test-data/generated-100k-12cols` (33.5 MiB combined, `||` delimiter, 100K rows × 12 columns)

## Executive Summary

The reconciliation hot path was dominated by **legacy spill code in `pipeline.py`** (per-row JSON + SHA256) while optimized modules (`spill.py`, `fingerprint.py`, `polars_spill.py`, `timing.py`) existed but were **not wired**. After integration, end-to-end time dropped from **~25 s → ~2.2 s** (default) and **~3.7 s** (forced disk spill) on the 100K multi-char dataset.

## Stage Timings (100K `||`, disk spill, no drilldown)

| Stage | Seconds | % of Total |
|-------|---------|------------|
| Source read (flat-file → Polars) | 1.40 | 38% |
| Target read | 1.10 | 30% |
| Serialization (binary spill encode) | 0.90 | 25% |
| Partition reconciliation (disk read + hash) | 0.75 | 21% |
| Disk read (reconcile phase) | 0.70 | 19% |
| **Total wall** | **3.66** | 100% |

*Stages overlap via `ThreadPoolExecutor` (source/target partition in parallel).*

## Stage Timings (100K `||`, default auto path)

| Stage | Seconds |
|-------|---------|
| Load source + target (Polars) | ~1.6 |
| Polars anti/inner joins | ~0.5 |
| **Total** | **~2.2** |

## Category Breakdown (Mandatory)

| Category | Measured | Notes |
|----------|----------|-------|
| File opening | &lt; 0.01 s | Per-partition handles cached |
| File reading | 2.5 s (spill) / 1.6 s (in-memory) | Dominated by multi-char flat parse |
| Network transfer | 0 s | Local FS benchmark |
| Deserialization | 0.7 s | Binary spill decode (reconcile) |
| Canonicalization | 0 s (vectorized) / 0.5 s (Python spill) | Polars expressions |
| Identity generation | 0 s (vectorized) | `concat_str` |
| Fingerprint generation | 0 s (vectorized) | Polars `hash()` |
| Partition calculation | 0 s (vectorized) | `hash() % N` |
| Partition writing | 0.9 s | Buffered binary (`PartitionWriter`) |
| Partition reading | 0.7 s | Sequential partition scan |
| Reconciliation | 0.75 s | In-memory dict per active partition |
| Column comparison | 0 s (equal files) | Only on fingerprint mismatch |
| Report generation | &lt; 0.001 s | Markdown optional |
| Garbage collection | Not observed | Peak RAM &lt; 45 MiB |
| Memory allocation | ~36 MiB peak (100K spill) | No dict-per-row on Polars path |
| Thread synchronization | &lt; 0.1 s | 2-worker partition pool |
| Queue waiting | N/A | Not on hot path |
| Lock contention | N/A | Partition files per bucket |
| Object creation | Reduced ~10× | Binary records vs JSON dicts |
| Serialization | 0.9 s | Compact `CB\x01` compare payload |
| JSON operations | 0 s (hot path) | Removed from spill |
| Disk I/O | ~1.6 s | Buffered 256 KiB flush |

## Profiling Commands

```bash
PYTHONPATH=pegasus-backend/src python scripts/profile_pipeline.py \
  --source test-data/generated-100k-12cols/source.csv \
  --target test-data/generated-100k-12cols/target.csv \
  --force-spill

PYTHONPATH=pegasus-backend/src python scripts/benchmark_reconciliation.py \
  --sizes 10000,100000 --force-spill
```

Flame graph (optional):

```bash
pip install flameprof
flameprof docs/benchmarks/profile-stats.pstats > docs/benchmarks/flame.svg
```

## Path Selection (Post-Optimization)

```
Combined size ≤ 64 MiB (auto_in_memory_max_bytes)?
├── YES → Polars in-memory join (~15–50 MB/s)
└── NO  → Spill path
         ├── Combined ≤ polars_spill_max_bytes AND NOT force_disk_spill?
         │   └── YES → polars_direct (same as in-memory)
         └── Disk spill
              ├── PyArrow delimiter OR loadable frame → Polars vectorized spill
              └── Else → Streaming Python (xxHash64 + binary spill)
```
