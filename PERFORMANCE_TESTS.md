# Performance Tests

**Date:** 2026-06-04

## Automated Tests

| Test | Location | Threshold |
|------|----------|-----------|
| 10K local throughput | `test_reconciliation_throughput.py::test_10k_local_throughput` | ≥ 8 MB/s |
| 100K auto path | `test_100k_local_auto_path_under_ten_seconds` | &lt; 3 s |
| 100K spill + drilldown | `test_100k_8col_spill_drilldown_under_eight_seconds` | &lt; 3.5 s |
| 100K disk spill | `test_100k_disk_spill_under_fifteen_seconds` | &lt; 8 s |
| GCS 100K no full download | `test_gcs_100k_performance.py` | &lt; 15 s, 0× `read_gcs_object_bytes` |
| 1M scale (optional) | `test_reconciliation_scale.py` | &lt; 5 s with `PEGASUS_RUN_SCALE_TESTS=1` |
| GCS TextIOWrapper | `test_gcs_stream_io.py` | must pass |
| Small CSV service | `test_validation_performance.py` | &lt; 5 s |
| 10K 12-col service | `test_validation_performance.py` | &lt; 5 s |

Scale thresholds with `PEGASUS_PERF_FACTOR` (default 1.0).

## Benchmark Scripts

```bash
# Reconciliation throughput matrix
PYTHONPATH=pegasus-backend/src python scripts/benchmark_reconciliation.py --sizes 10000,100000

# Stage timings + cProfile
PYTHONPATH=pegasus-backend/src python scripts/profile_pipeline.py \
  --source test-data/generated-100k-8cols/source.csv \
  --target test-data/generated-100k-8cols/target.csv

# Hash algorithms
PYTHONPATH=pegasus-backend/src python scripts/benchmark_hash_algorithms.py

# Top functions report
PYTHONPATH=pegasus-backend/src python scripts/generate_top50_functions.py
```

## Datasets

| Dataset | Rows | Cols | Delimiter | Use |
|---------|------|------|-----------|-----|
| `generated-100k-8cols` | 100K / 70K | 8 | `\|\|` | Mismatch-heavy audit |
| `generated-10k-12cols` | 10K | 12 | `\|\|` | CI throughput |
| `generated-100k-12cols` | 100K | 12 | `\|\|` | Wide-ish (if present) |

## Run performance suite

```bash
cd /home/ansh.raj/Pegasus
PYTHONPATH=pegasus-backend/src pytest pegasus-backend/tests/test_reconciliation_throughput.py -m performance -v
```

## CI Notes

Register `@pytest.mark.performance` in `pyproject.toml` / `pytest.ini` to silence unknown mark warning.

## Before/after gate (100K 8-col spill+drill)

| Build | Median time |
|-------|-------------|
| Before encode + column filter fixes | ~12.2 s |
| After | **~6.9 s** |

Add regression: `assert elapsed < 8.0` on `generated-100k-8cols` spill+drill when dataset present.
