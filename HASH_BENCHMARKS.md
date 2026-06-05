# Hash Benchmarks

**Script:** `scripts/benchmark_hash_algorithms.py`  
**Workload:** 100,000 rows × 7 columns, 5 iterations, join key materialized as strings.

## Results (hashes per second, higher is better)

| Algorithm | Hashes/sec | Digest | Collision risk | Verdict |
|-----------|------------|--------|----------------|---------|
| **xxhash128** | **3,672,999** | 16 B | Low for fingerprint | Fastest raw |
| **xxhash64** | **2,834,238** | 8 B | Low for fingerprint | **Production default** |
| sha1 (trunc 8B) | 2,176,617 | 8 B | Higher | Legacy |
| crc64 | 1,194,376 | 8 B | Higher | Weak |
| pegasus `row_fingerprint_bytes` (xxhash64) | 978,173 | 8 B | Low | Canonicalization overhead |
| sha256 | 393,192 | 32 B | Lowest | Too slow |

## Production Choice

- **Keep `xxhash64`** via Polars `Expr.hash()` on concatenated canonical compare columns (in-memory and spill).
- **Do not** per-row call Python `row_fingerprint_from_parts` on hot paths (streaming fallback only).

## Reconciliation alignment

Mismatch detection uses **equality of 64-bit fingerprints**, not cryptographic proof. xxhash64 is acceptable; upgrade to xxhash128 only if fingerprint collisions become observable (none in test suites).

## Rows/sec (fingerprint only, synthetic)

~3M hashes/sec (xxhash128) → at 7 columns × 100K rows, fingerprint stage &lt;40 ms when vectorized in Polars.
