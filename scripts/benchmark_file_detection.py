#!/usr/bin/env python3
"""Benchmark file detection: legacy extension-only vs multi-layer pipeline."""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

# Allow running from repo root without install
_REPO = Path(__file__).resolve().parents[1]
_BACKEND_SRC = _REPO / "pegasus-backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from pegasus.validation.file_detection import detect_file  # noqa: E402
from pegasus.validation.file_pairing import extensions_for_format  # noqa: E402


def _legacy_detect(path: Path, declared_format: str = "csv") -> dict:
    """Previous behavior: extension allowlist + declared format only."""
    ext = path.suffix.lower()
    allowed = extensions_for_format(declared_format)
    return {
        "detected_type": declared_format,
        "extension": ext,
        "extension_allowed": (not ext) or (ext in allowed),
        "confidence": 25 if ext in allowed else 5,
    }


def _bench(fn, path: Path, *, iterations: int) -> dict:
    times: list[float] = []
    peak = 0
    for _ in range(iterations):
        tracemalloc.start()
        t0 = time.perf_counter()
        fn(path)
        times.append(time.perf_counter() - t0)
        _, peak_now = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peak = max(peak, peak_now)
    return {
        "mean_ms": statistics.mean(times) * 1000,
        "p95_ms": sorted(times)[int(0.95 * len(times)) - 1] * 1000 if len(times) > 1 else times[0] * 1000,
        "peak_kb": peak / 1024,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Files to benchmark")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--format-hint", default="csv")
    args = parser.parse_args()

    print(f"{'file':<40} {'legacy_mean_ms':>14} {'pipeline_mean_ms':>16} {'bytes_read':>10}")
    print("-" * 85)

    legacy_tot: list[float] = []
    pipe_tot: list[float] = []

    for path in args.files:
        if not path.is_file():
            print(f"skip (not file): {path}")
            continue
        leg = _bench(lambda p: _legacy_detect(p, args.format_hint), path, iterations=args.iterations)
        pip = _bench(lambda p: detect_file(p, user_format_hint=args.format_hint), path, iterations=args.iterations)
        report = detect_file(path, user_format_hint=args.format_hint)
        legacy_tot.append(leg["mean_ms"])
        pipe_tot.append(pip["mean_ms"])
        print(
            f"{path.name:<40} {leg['mean_ms']:>14.3f} {pip['mean_ms']:>16.3f} {report.bytes_read:>10}"
        )

    if legacy_tot:
        print("-" * 85)
        print(f"{'TOTAL AVG':<40} {statistics.mean(legacy_tot):>14.3f} {statistics.mean(pipe_tot):>16.3f}")
        speedup = statistics.mean(legacy_tot) / max(statistics.mean(pipe_tot), 1e-9)
        print(f"Pipeline vs legacy mean latency ratio: {speedup:.2f}x (values <1 mean pipeline slower)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
