#!/usr/bin/env python3
"""Benchmark fingerprint hash algorithms for reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pegasus-backend" / "src"))

from pegasus.validation.pipeline.fingerprint import row_fingerprint_bytes

try:
    import blake3 as _blake3

    _HAS_BLAKE3 = True
except ImportError:
    _HAS_BLAKE3 = False

try:
    import mmh3 as _mmh3

    _HAS_MMH3 = True
except ImportError:
    _HAS_MMH3 = False

try:
    import xxhash as _xxhash

    _HAS_XXHASH = True
except ImportError:
    _HAS_XXHASH = False


def _sample_parts(n: int) -> list[str]:
    return [f"value-{i % 97}" for i in range(n)]


def _bench(name: str, fn, parts: list[str], *, iterations: int) -> dict:
    times: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn(parts)
        times.append(time.perf_counter() - t0)
    mean = statistics.mean(times)
    return {
        "algorithm": name,
        "mean_seconds": round(mean, 6),
        "hashes_per_second": round(len(parts) / mean, 0),
        "digest_bytes": 8,
    }


def _sha256(parts: list[str]) -> bytes:
    return hashlib.sha256("\x1f".join(parts).encode()).digest()


def _sha1(parts: list[str]) -> bytes:
    return hashlib.sha1("\x1f".join(parts).encode()).digest()[:8]


def _crc64(parts: list[str]) -> bytes:
    data = "\x1f".join(parts).encode()
    return zlib.crc32(data).to_bytes(4, "big") + zlib.crc32(data[::-1]).to_bytes(4, "big")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--columns", type=int, default=11)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "benchmarks" / "hash-benchmark.json")
    args = parser.parse_args()

    record = {f"c{i}": f"v{i}" for i in range(args.columns)}
    columns = list(record)
    parts = _sample_parts(args.columns)

    algos: list[tuple[str, object]] = [
        ("sha256", _sha256),
        ("sha1", _sha1),
        ("crc64", _crc64),
    ]
    if _HAS_XXHASH:
        algos.extend([
            ("xxhash64", lambda p: _xxhash.xxh64("\x1f".join(p).encode()).digest()),
            ("xxhash128", lambda p: _xxhash.xxh128("\x1f".join(p).encode()).digest()[:8]),
        ])
    if _HAS_MMH3:
        algos.append(("murmurhash3", lambda p: _mmh3.hash128("\x1f".join(p), signed=False).to_bytes(16, "big")[:8]))
    if _HAS_BLAKE3:
        algos.append(("blake3", lambda p: _blake3.blake3("\x1f".join(p).encode()).digest()[:8]))

    results: list[dict] = []
    for _ in range(args.rows):
        pass
    for name, fn in algos:
        results.append(_bench(name, fn, parts, iterations=args.iterations))

    results.append(
        _bench(
            "pegasus_xxhash64",
            lambda p: row_fingerprint_bytes(record, columns, algorithm="xxhash64"),
            parts,
            iterations=args.iterations,
        )
    )

    results.sort(key=lambda r: r["hashes_per_second"], reverse=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    print(f"{'algorithm':<20} {'hashes/s':>12}")
    for row in results:
        print(f"{row['algorithm']:<20} {row['hashes_per_second']:>12,.0f}")
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
