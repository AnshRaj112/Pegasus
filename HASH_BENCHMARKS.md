# Hash Benchmarks

**Date:** 2026-06-04  
**Harness:** `scripts/benchmark_hash_algorithms.py`  
**Raw results:** `docs/benchmarks/hash-benchmark.json`

## Methodology

- 7 compare columns, synthetic string values joined with `\x1f`
- 5 iterations, mean throughput reported
- Pegasus path uses `row_fingerprint_bytes` (canonical + join + xxhash)

## Results (hashes per second, higher is better)

| Algorithm | Hashes/s | Digest | Notes |
|-----------|----------|--------|-------|
| **xxhash128** | 3,748,528 | 8 bytes (truncated) | Fastest in micro-benchmark |
| **xxhash64** | 2,800,224 | 8 bytes | **Production default** |
| crc64 (zlib composite) | 2,315,121 | 8 bytes | Acceptable |
| sha1 | 2,268,014 | 8 bytes (truncated) | Faster than SHA256, weaker |
| sha256 | 1,146,676 | 32 bytes | 2.4× slower than xxhash64 |
| pegasus_xxhash64 | 960,720 | 8 bytes | Includes per-column `canonical()` |

## Production Usage

| Path | Hash function |
|------|---------------|
| Polars in-memory / spill | Polars `Expr.hash()` on canonicalized `concat_str` |
| Python streaming fallback | `xxhash64` via `row_fingerprint_from_parts` |
| Partition ID | `xxhash64(identity) % N` (was MD5) |

## Recommendation

**Keep `xxhash64`** for Python fallback fingerprints. Polars vectorized `hash()` already matches this class.

- **Do not** revert to SHA256 for hot paths — proven ~2.4× slower with no reconciliation benefit at 100K–100M row scale.
- **xxhash128** is faster in isolation but provides no material gain when Polars hashing dominates; 64-bit collision risk is acceptable for equality screening (re-run with column drilldown on mismatch).
- **BLAKE3 / MurmurHash3**: not in default deps; optional if xxhash unavailable.

## Rows/sec equivalence (7 columns)

At 2.8M hashes/s (xxhash64 join benchmark), fingerprint-only throughput ≈ **400K rows/s** — not the limiting factor when parsing/serialization dominate.

## Re-run

```bash
PYTHONPATH=pegasus-backend/src python scripts/benchmark_hash_algorithms.py \
  --rows 200000 --columns 7
```
