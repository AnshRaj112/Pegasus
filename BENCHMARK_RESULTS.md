# Benchmark Results

**Date:** 2026-06-04  
**Scripts:** `scripts/benchmark_reconciliation.py`, `scripts/benchmark_hash_algorithms.py`

## Before / After — Primary Scenario (100K `||`, 33.5 MiB)

| Metric | Before (legacy pipeline) | After | Change |
|--------|------------------------|-------|--------|
| Wall time (default) | 24.8 s | **2.20 s** | **−91%** |
| Wall time (disk spill) | 24.8 s | **3.66 s** | **−85%** |
| Spill format | JSON + SHA256 hex | Binary + xxHash64 | — |
| Serialization (est.) | ~60 µs/row JSON | ~9 µs/row binary | ~6× |
| Fingerprint | SHA256 Python | Polars hash / xxHash64 | ~16× |
| Partition scan | 0..2047 all buckets | Active files only | ~32× fewer on small data |

## Reconciliation Harness (`benchmark_reconciliation.py`)

### Single-byte `|` generated data

| Rows | Path | Time (s) | Rows/s | MB/s |
|------|------|----------|--------|------|
| 10K | auto | 0.45 | 22,011 | 1.6 |
| 10K | spill | 0.85 | 11,743 | 0.9 |
| 10K | spill+drilldown | 2.87 | 2,874 | 0.3 |
| 100K | auto | 0.35 | 289,710 | 22.9 |
| 100K | spill | 7.36 | 13,592 | 1.1 |
| 100K | spill+drilldown | 9.14 | 2,692 | 0.9 |

### Multi-char `||` production test data

| Rows | Path | Time (s) | MB/s |
|------|------|----------|------|
| 10K | in_memory | 0.27 | 14.1 |
| 10K | spill_binary | 0.48 | 7.9 |
| 100K | in_memory | 2.20 | 15.2 |
| 100K | spill_binary | 3.66 | 9.2 |

## Hash Algorithm Benchmark

See `docs/benchmarks/hash-benchmark.json`.

| Algorithm | hashes/s | Selected |
|-----------|----------|----------|
| xxhash128 | 2,966,399 | No (overkill) |
| xxhash64 | 1,699,524 | **Yes (default)** |
| sha256 | 1,275,126 | Compliance-only |

## Memory

| Scenario | Peak RAM |
|----------|----------|
| 100K auto | ~5 MiB (tracemalloc) |
| 100K spill | ~37 MiB |

## Artifacts

- `docs/benchmarks/reconciliation-results.json`
- `docs/benchmarks/hash-benchmark.json`
- `docs/benchmarks/profile-timings.json`
- `docs/benchmarks/profile-stats.txt`

## Reproduce

```bash
PYTHONPATH=pegasus-backend/src python scripts/benchmark_reconciliation.py --sizes 10000,100000
PYTHONPATH=pegasus-backend/src python scripts/benchmark_hash_algorithms.py
```
