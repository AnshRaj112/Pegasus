# File Detection Benchmark Results

Environment: Linux, Python 3.x, `pegasus-backend` on `PYTHONPATH=src`.  
Iterations: 50 per file (100 in prior doc run).  
Date: 2026-06-03.

## Methodology

| Path | What it measures |
|------|------------------|
| **Legacy** | `extensions_for_format(declared_format)` + suffix check only (~0.01 ms) |
| **Pipeline** | Full `detect_file()` — single 64 KiB read + 9 layers |

Legacy path reflects **pre-change** routing: users declare `file_format`; the server trusts it with extension allowlists only.

## Before (legacy only — pre-implementation)

| File | Legacy mean (ms) | Pipeline | Bytes read |
|------|------------------|----------|------------|
| `test-data/generated-100k-12cols/source.csv` | 0.013 | N/A (module missing) | 0 |
| `test-data/entity-inference/unknown-entity/ledgerx_28052026_171700_source.csv` | 0.013 | N/A | 0 |

## After (pipeline implemented)

| File | Legacy mean (ms) | Pipeline mean (ms) | Bytes read |
|------|------------------|--------------------|------------|
| `test-data/generated-100k-12cols/source.csv` | 0.010 | 102.9 | 65536 |
| `test-data/entity-inference/unknown-entity/ledgerx_28052026_171700_source.csv` | 0.008 | 1.3 | 97 |

**Average:** legacy 0.009 ms vs pipeline 52.1 ms (dominated by 64 KiB structured/schema heuristics on wide CSV).

## Interpretation

- Legacy detection is essentially free but **does not** verify content, compression, or encoding.
- Pipeline cost is **bounded** (~1–103 ms per file, ≤64 KiB I/O) regardless of file size on disk (100GB+ files still read ≤64 KiB).
- Dominant cost on wide CSV samples is structured/schema heuristics over 64 KiB UTF-8 text, not disk I/O.
- **Memory:** tracemalloc peak during benchmark runs stayed under 1 MiB per invocation (see `scripts/benchmark_file_detection.py`).

## Reproduce

```bash
python scripts/benchmark_file_detection.py \
  test-data/generated-100k-12cols/source.csv \
  test-data/entity-inference/unknown-entity/ledgerx_28052026_171700_source.csv \
  --iterations 50
```

## Follow-up optimizations (not yet implemented)

- Skip schema layer when `file_format` hint confidence ≥ 95
- Lazy-load `python-magic` once per worker process
- Merge delimiter detection (512 KiB) with structured layer to avoid duplicate reads on validate path
