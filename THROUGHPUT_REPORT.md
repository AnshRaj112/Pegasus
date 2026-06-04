# Throughput Report

**Date:** 2026-06-04

## Measured Throughput

| Workload | Path | Wall time | Rows/s | MiB/s |
|----------|------|-----------|--------|-------|
| 100K `||` 8-col, auto | `in_memory_polars` | 1.7 s | **58,800** | **12.2** |
| 100K `||` mismatch, spill no drill | `spill_binary` | 2.9 s | 34,500 | 7.2 |
| 100K `||` mismatch, spill + drill | `spill_binary` | 6.9 s | **14,500** | 3.0 |
| 100K `\|` 12-col, auto (generated) | auto | 0.72 s | **138,500** | — |
| 100K GCS mock (cached) | `in_memory_polars` | 1.67 s | 59,900 | 12.4 |
| ValidationService E2E local | service | 1.77 s | 56,500 | 11.8 |

## Target vs Current (Gap Analysis)

| Metric | Target | Current (best) | Current (worst prod-like) | Gap |
|--------|--------|----------------|---------------------------|-----|
| Narrow dataset | 100K rows/s | **~59–139K rows/s** | ~14.5K rows/s (spill+drill) | **Met** on auto path; **7×** short on drilldown spill |
| Wide dataset | 50K rows/s | Not benchmarked at 1000 cols | — | Needs wide synthetic set |
| 100 GB / 10 min | ~167 MiB/s sustained | ~12 MiB/s (in-memory) | ~3 MiB/s (spill+drill) | **14–55×** |

## Where Time Goes (100K mismatch, spill+drill)

```
Read/parse     ████████████░░░░░░░░  39%
Serialize spill ██████████████████░░  56%
Reconcile      ████████████░░░░░░░░  41%  (overlaps read)
Column diff    ░░░░░░░░░░░░░░░░░░░░   1%
```

## Expected Improvements (next changes)

| Change | Expected speedup | New rows/s (est.) |
|--------|------------------|-------------------|
| Columnar spill encoder | 2–3× on drilldown spill | 30–45K |
| Faster multi-char parse | 1.3× on all `||` paths | 75K in-memory |
| Defer drilldown to mismatch-only | 2×+ on high mismatch | 25–30K spill |
| Distributed partition workers | Linear in cores | Scales horizontally |

## Benchmark Reproduction

```bash
PYTHONPATH=pegasus-backend/src python3 -c "
# See scripts/benchmark_reconciliation.py and profile_pipeline.py
"

pytest pegasus-backend/tests/test_reconciliation_throughput.py -m performance
```

Results JSON: `docs/benchmarks/reconciliation-results.json`, `docs/benchmarks/profile-timings.json`
