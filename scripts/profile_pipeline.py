#!/usr/bin/env python3
"""Profile reconciliation pipeline stages and emit cProfile stats."""

from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import sys
import tempfile
import time
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pegasus-backend" / "src"))

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline

COMPARE_COLS = [
    "sku", "amount", "region", "attr4", "attr5", "attr6",
    "attr7", "attr8", "attr9", "attr10", "attr11",
]


def _run(source: Path, target: Path, *, force_spill: bool, drilldown: bool) -> dict:
    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=0 if force_spill else 64 * 1024 * 1024,
        enable_column_drilldown=drilldown,
        force_disk_spill=force_spill,
        fingerprint_algorithm="xxhash64",
    )
    src_ad = FileDelimitedAdapter(source, delimiter="||")
    tgt_ad = FileDelimitedAdapter(target, delimiter="||")
    schema_cols = src_ad.get_schema().column_names
    compare_columns = [c for c in COMPARE_COLS if c in schema_cols] or [
        c for c in schema_cols if c != "id"
    ]
    with tempfile.TemporaryDirectory() as td:
        pipe = TabularReconciliationPipeline(
            src_ad,
            tgt_ad,
            identity_columns=["id"],
            compare_columns=compare_columns,
            config=cfg,
        )
        t0 = time.perf_counter()
        result = pipe.run(workspace=Path(td))
    elapsed = time.perf_counter() - t0
    return {
        "elapsed_seconds": round(elapsed, 4),
        "rows": result.source_row_count,
        "path": result.extra_stats.get("path"),
        "timings": result.extra_stats.get("timings", {}),
        "stages": result.extra_stats.get("stages", []),
        "stage_report": result.extra_stats.get("stage_report", ""),
        "bytes": source.stat().st_size + target.stat().st_size,
    }


def _top_functions(profile_path: Path, *, limit: int = 25) -> list[dict]:
    stream = StringIO()
    stats = pstats.Stats(str(profile_path), stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(limit)
    rows: list[dict] = []
    for line in stream.getvalue().splitlines():
        if line.strip() and not line.startswith(" ") and "function calls" not in line:
            continue
        parts = line.split()
        if len(parts) >= 6 and parts[0].replace(".", "", 1).isdigit():
            rows.append({"line": line.strip()})
    return rows[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--force-spill", action="store_true")
    parser.add_argument("--no-drilldown", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "benchmarks" / "profile-stats.txt")
    parser.add_argument("--json-output", type=Path, default=ROOT / "docs" / "benchmarks" / "profile-timings.json")
    args = parser.parse_args()

    prof_path = args.output.with_suffix(".pstats")
    cfg_drill = not args.no_drilldown
    with cProfile.Profile() as prof:
        summary = _run(args.source, args.target, force_spill=args.force_spill, drilldown=cfg_drill)
        prof.dump_stats(str(prof_path))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    stream = StringIO()
    pstats.Stats(str(prof_path), stream=stream).sort_stats("cumulative").print_stats(30)
    args.output.write_text(stream.getvalue(), encoding="utf-8")
    args.json_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    stage_report = summary.get("stage_report")
    if stage_report:
        print("\n" + stage_report)
    print(f"Wrote {args.output} and {prof_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
