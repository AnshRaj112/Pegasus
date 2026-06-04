# Performance Tests

## Automated Tests

| Test file | What it covers |
|-----------|----------------|
| `pegasus-backend/tests/test_reconciliation_throughput.py` | MB/s and latency floors (10K, 100K) |
| `pegasus-backend/tests/test_validation_performance.py` | Service-level CSV validation |
| `pegasus-backend/tests/test_pipeline_performance_modules.py` | Binary spill + fingerprint unit tests |
| `pegasus-backend/tests/test_gcs_in_memory_fast_path.py` | GCS → Polars fast path |

## Scenarios Matrix

| Scenario | Dataset | Expected path | Assertion |
|----------|---------|---------------|-----------|
| 10K rows, local `||` | `generated-10k-12cols` | in_memory / polars_direct | ≥ 8 MB/s |
| 100K rows, local `||` | `generated-100k-12cols` | in_memory | &lt; 10 s |
| 100K disk spill | same | spill_binary | &lt; 15 s |
| Wide table 1000 cols | *generate when available* | TBD | TBD |
| Duplicate / missing / extra | mutation fixtures | correct counts | functional |
| GCS | `test_gcs_in_memory_fast_path` | cached prefix | completes |

## Run Performance Suite

```bash
cd pegasus-backend
PYTHONPATH=src pytest -m performance tests/test_reconciliation_throughput.py -v

# Relax on slow hardware:
PEGASUS_PERF_FACTOR=2.0 PYTHONPATH=src pytest -m performance tests/test_reconciliation_throughput.py -v
```

## Target Thresholds (from requirements)

| Size | Target | Test coverage |
|------|--------|---------------|
| 10K | smoke | `test_10k_local_throughput` |
| 100K | &lt; 10 s auto | `test_100k_local_auto_path_under_ten_seconds` |
| 100K spill | &lt; 15 s | `test_100k_disk_spill_under_fifteen_seconds` |
| 1M+ | not yet | Add when fixtures exist |
| Wide 1000 cols | not yet | Generator script needed |
| GCS | partial | Extend with cloud CI job |

## Test Data Generation

```bash
python scripts/generate_validation_data.py   # if present
# Or use existing:
# test-data/generated-10k-12cols/
# test-data/generated-100k-12cols/
```

## CI Integration

Mark slow tests with `@pytest.mark.performance` and run on dedicated runner:

```yaml
- run: PYTHONPATH=pegasus-backend/src pytest -m performance pegasus-backend/tests/test_reconciliation_throughput.py
```

Fail build when throughput regresses below documented floors in `THROUGHPUT_REPORT.md`.
