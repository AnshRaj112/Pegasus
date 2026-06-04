# Benchmark Results

**Date:** 2026-06-04  
**Machine:** 4-core Linux, Python 3.12

## 100K × 8 columns (`generated-100k-8cols`, `||` delimiter, mismatch-heavy)

| Configuration | Wall time | Rows/s | Path |
|---------------|-----------|--------|------|
| **After** — auto (default) | 1.70 s | 58,824 | `in_memory_polars` |
| **After** — spill, no drilldown | 2.94 s | 34,014 | `spill_binary` |
| **After Phase 1** — spill + drilldown | **6.95 s** (median of 3) | 14,388 | `spill_binary` |
| **After Phase 2** — spill + drilldown | **~5.0 s** (median of 3) | ~20,000 | `spill_binary_lazy_drilldown` |
| **Before** — spill + drilldown | 12.24 s | 8,170 | `spill_binary` |
| User-reported (prior) | 16.9 s | 5,917 | Likely spill+drill + overhead |
| User-reported (older) | 28.3 s | 3,534 | Pre binary-spill integration |

## 100K × 12 columns (generated in benchmark script, `\|` delimiter)

| Configuration | Wall time | Rows/s |
|---------------|-----------|--------|
| Auto | 0.72 s | 138,530 |
| Spill | 3.79 s | 26,387 |
| Spill + drilldown | ~21.6 s | 4,633 |

## ValidationService E2E (100K 8-col local)

| Metric | Value |
|--------|-------|
| Wall time | 1.77 s |
| Rows/s | 56,497 |

## GCS (mocked, cached, 100K 8-col)

| Metric | Value |
|--------|-------|
| Downloads | 2 |
| Wall time | 1.67 s |
| Path | `in_memory_polars` |

## Artifacts

- `docs/benchmarks/reconciliation-results.json`
- `docs/benchmarks/profile-timings.json`
- `docs/benchmarks/hash-benchmark.json`
- `docs/benchmarks/profile-stats.pstats`

## Commands

```bash
PYTHONPATH=pegasus-backend/src python scripts/benchmark_reconciliation.py --sizes 100000
PYTHONPATH=pegasus-backend/src python scripts/profile_pipeline.py \
  --source test-data/generated-100k-8cols/source.csv \
  --target test-data/generated-100k-8cols/target.csv
```
