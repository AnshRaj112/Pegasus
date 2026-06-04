#!/usr/bin/env python3
"""Reconciliation pipeline benchmark harness.

Usage:
    PYTHONPATH=pegasus-backend/src python scripts/benchmark_reconciliation.py
    PYTHONPATH=pegasus-backend/src python scripts/benchmark_reconciliation.py --sizes 10000,100000
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import resource
import sys
import tempfile
import time
import tracemalloc
from dataclasses import asdict, dataclass
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


@dataclass
class BenchResult:
    rows: int
    elapsed_seconds: float
    rows_per_second: float
    mb_per_second: float
    peak_memory_mb: float
    source_bytes: int
    target_bytes: int
    partitions: int
    path: str
    timings: dict


def _generate_csv(path: Path, rows: int, *, mismatch_every: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="|", lineterminator="\n")
        w.writerow(["id", *COMPARE_COLS])
        for i in range(rows):
            row = [str(i), f"SKU{i}", str(i * 1.5), "US", "a", "b", "c", "d", "e", "f", "g", "h"]
            w.writerow(row)


def _generate_pair(work: Path, rows: int) -> tuple[Path, Path]:
    src = work / f"src_{rows}.csv"
    tgt = work / f"tgt_{rows}.csv"
    _generate_csv(src, rows)
    _generate_csv(tgt, rows)
    return src, tgt


def _run_bench(src: Path, tgt: Path, *, force_spill: bool, drilldown: bool) -> BenchResult:
    cfg = TabularPipelineConfig(
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=0 if force_spill else 64 * 1024 * 1024,
        enable_column_drilldown=drilldown,
        chunk_rows=min(50_000, max(10_000, src.stat().st_size // 200)),
        fingerprint_algorithm="xxhash64",
        force_disk_spill=force_spill,
    )
    src_ad = FileDelimitedAdapter(src, delimiter="|")
    tgt_ad = FileDelimitedAdapter(tgt, delimiter="|")
    tracemalloc.start()
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        pipe = TabularReconciliationPipeline(
            src_ad,
            tgt_ad,
            identity_columns=["id"],
            compare_columns=COMPARE_COLS,
            config=cfg,
        )
        result = pipe.run(workspace=Path(td))
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    total_bytes = src.stat().st_size + tgt.stat().st_size
    rows = result.source_row_count
    return BenchResult(
        rows=rows,
        elapsed_seconds=round(elapsed, 4),
        rows_per_second=round(rows / elapsed, 1),
        mb_per_second=round(total_bytes / elapsed / 1024 / 1024, 2),
        peak_memory_mb=round(peak / 1024 / 1024, 2),
        source_bytes=src.stat().st_size,
        target_bytes=tgt.stat().st_size,
        partitions=result.partitions_processed,
        path="spill" if force_spill else "auto",
        timings=result.extra_stats.get("timings", {}),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Pegasus reconciliation pipeline")
    parser.add_argument(
        "--sizes",
        default="10000,100000,1000000",
        help="Comma-separated row counts",
    )
    parser.add_argument("--output", default=str(ROOT / "docs" / "benchmarks" / "reconciliation-results.json"))
    parser.add_argument("--force-spill", action="store_true", help="Disable in-memory fast path")
    args = parser.parse_args()
    sizes = [int(s.strip()) for s in args.sizes.split(",") if s.strip()]

    results: list[dict] = []
    with tempfile.TemporaryDirectory() as work_dir:
        work = Path(work_dir)
        for n in sizes:
            print(f"Generating {n:,} row dataset...", flush=True)
            src, tgt = _generate_pair(work, n)
            print(f"  Running auto path...", flush=True)
            auto = _run_bench(src, tgt, force_spill=False, drilldown=True)
            print(f"  {n:,} rows auto: {auto.rows_per_second:,.0f} rows/s ({auto.elapsed_seconds}s)")
            results.append(asdict(auto))
            if args.force_spill or n <= 100_000:
                print(f"  Running spill path...", flush=True)
                spill = _run_bench(src, tgt, force_spill=True, drilldown=False)
                spill.path = "spill_no_drilldown"
                print(f"  {n:,} rows spill: {spill.rows_per_second:,.0f} rows/s ({spill.elapsed_seconds}s)")
                results.append(asdict(spill))
                spill_dd = _run_bench(src, tgt, force_spill=True, drilldown=True)
                spill_dd.path = "spill_drilldown"
                print(f"  {n:,} rows spill+drilldown: {spill_dd.rows_per_second:,.0f} rows/s")
                results.append(asdict(spill_dd))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "host": os.uname().nodename,
        "cpu_count": os.cpu_count(),
        "fingerprint_algorithm": "xxhash64",
        "spill_format": "binary_v1",
        "results": results,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
