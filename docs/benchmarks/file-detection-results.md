# File Detection Benchmark Results

Environment: Linux, Python 3.x, `pegasus-backend` on `PYTHONPATH=src`.  
Iterations: 100 per file.  
Date: 2026-06-03.

## Methodology

| Path | What it measures |
|------|------------------|
| **Legacy** | `extensions_for_format(declared_format)` + suffix check only (~0.01 ms) |
| **Pipeline** | Full `detect_file()` — single 64 KiB read + 9 layers |

Legacy path reflects **pre-change** routing: users declare `file_format`; the server trusts it with extension allowlists only.

## Results

| File | Legacy mean (ms) | Pipeline mean (ms) | Bytes read |
|------|------------------|--------------------|------------|
| `test-data/generated-100k-12cols/source.csv` | 0.013 | 69.6 | 65536 |
| `test-data/entity-inference/unknown-entity/ledgerx_28052026_171700_source.csv` | 0.013 | 3.8 | 97 |

**Average:** legacy 0.013 ms vs pipeline 36.7 ms (dominated by 64 KiB sample on large-prefix path).

## Interpretation

- Legacy detection is essentially free but **does not** verify content, compression, or encoding.
- Pipeline cost is **bounded** (~3–70 ms per file, ≤64 KiB I/O) regardless of file size on disk (100GB+ files still read ≤64 KiB).
- Dominant cost on wide CSV samples is structured/schema heuristics over 64 KiB UTF-8 text, not disk I/O.
- **Memory:** tracemalloc peak during benchmark runs stayed under 1 MiB per invocation (see `scripts/benchmark_file_detection.py`).

## Reproduce

```bash
python scripts/benchmark_file_detection.py \
  test-data/generated-100k-12cols/source.csv \
  test-data/entity-inference/unknown-entity/ledgerx_28052026_171700_source.csv \
  --iterations 100
```

## Follow-up optimizations (not yet implemented)

- Skip schema layer when `file_format` hint confidence ≥ 95
- Lazy-load `python-magic` once per worker process
- Merge delimiter detection (512 KiB) with structured layer to avoid duplicate reads on validate path
