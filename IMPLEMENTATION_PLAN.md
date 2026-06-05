# Implementation Plan — Phase 4

## Completed

| Item | Status |
|------|--------|
| Architecture docs (9 files) | Done |
| ARW1 Arrow IPC spill | Done |
| Polars vectorized partition reconcile | Done |
| Lazy drilldown (fingerprint-only + batch keys) | Done |
| GCS streaming (`gcs_stream.py`, no full download) | Done |
| Column projection (`include_columns`) | Done |
| Process-pool partition reconcile | Done |
| Streaming batch spill (large local files) | Done |
| Performance tests 100K + optional 1M scale | Done |
| `_ReadAheadBinaryIO` TextIOWrapper fix | Done |

## Phase 4c — Remaining

| Priority | Task |
|----------|------|
| P0 | GCS streaming batch spill (mirror `partition_side_streaming_batches`) |
| P0 | 10M / 100GB benchmark on target hardware |
| P1 | Drilldown re-stream from adapter (drop O(n) frame cache on large lazy path) |
| P1 | K8s partition worker Job spec |
| P2 | Wide (1000 col) generated dataset + projection test |
| P3 | Multi-char delimiter SIMD / Rust tokenizer benchmarks |

## Config

```python
TabularPipelineConfig(
    use_arrow_ipc_spill=True,
    fingerprint_only_spill=True,
    lazy_column_drilldown=True,
    partition_reconcile_workers=0,  # auto: min(8, cpu-1)
    streaming_spill_min_bytes=64 * 1024 * 1024,
)
```

## Verification

```bash
cd pegasus-backend
PYTHONPATH=src python -m pytest tests/test_reconciliation_throughput.py tests/test_gcs_stream_io.py -q
PEGASUS_RUN_SCALE_TESTS=1 PYTHONPATH=src python -m pytest tests/test_reconciliation_scale.py -m performance -v
PYTHONPATH=src python ../scripts/benchmark_reconciliation.py --sizes 100000,1000000
```
