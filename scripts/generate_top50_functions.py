#!/usr/bin/env python3
"""Emit TOP_50_FUNCTIONS.md from a cProfile .pstats file."""

from __future__ import annotations

import argparse
import pstats
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pstats",
        type=Path,
        default=ROOT / "docs" / "benchmarks" / "profile-stats.pstats",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "TOP_50_FUNCTIONS.md",
    )
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    stats = pstats.Stats(str(args.pstats))
    stats.calc_callees()
    stats.sort_stats("tottime")

    rows: list[tuple] = []
    for func, stat in stats.stats.items():
        cc, nc, tt, ct, callers = stat
        filename, line, name = func
        rows.append((tt, ct, nc, name, f"{filename}:{line}"))

    total = sum(r[0] for r in rows) or 1.0
    rows.sort(key=lambda r: r[0], reverse=True)
    rows = rows[: args.limit]

    lines = [
        "# Top 50 Functions (cProfile by `tottime`)",
        "",
        f"**Source:** `{args.pstats}`",
        "",
        "| Rank | Function | File | Call Count | Total Time (s) | Avg Time (ms) | % Runtime |",
        "|------|----------|------|------------|----------------|-----------------|-----------|",
    ]
    for i, (tt, ct, nc, name, loc) in enumerate(rows, 1):
        avg_ms = (tt / nc * 1000) if nc else 0.0
        pct = tt / total * 100
        lines.append(
            f"| {i} | `{name}` | `{loc}` | {nc:,} | {tt:.4f} | {avg_ms:.4f} | {pct:.1f}% |"
        )

    lines.extend(
        [
            "",
            "Sorted by **self time** (`tottime`). Cumulative time in parent report.",
            "",
        ]
    )
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
