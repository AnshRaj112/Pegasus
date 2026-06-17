#!/usr/bin/env python3
# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T11:17:59Z
# --- END GENERATED FILE METADATA ---

"""Benchmark native multichar spill + full reconciliation at scale."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from pegasus.core.workload_budget import plan_workload_budget
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.config import TabularPipelineConfig
from pegasus.validation.pipeline.pipeline import TabularReconciliationPipeline
from pegasus.validation.readers.native_multichar import native_extension_available

REPO = Path("/home/ansh.raj/Pegasus")
FIXTURES = [
    {
        "label": "100k-8cols",
        "source": REPO / "test-data/generated-100k-8cols/source.csv",
        "target": REPO / "test-data/generated-100k-8cols/target.csv",
        "compare": ["sku", "amount", "region", "attr4", "attr5", "attr6", "attr7"],
        "rows": 100_000,
    },
    {
        "label": "1m",
        "source": REPO / "test-data/generated-1m/source.csv",
        "target": REPO / "test-data/generated-1m/target.csv",
        "compare": ["sku", "amount", "region"],
        "rows": 1_000_000,
    },
    {
        "label": "10m",
        "source": REPO / "test-data/generated-10m/source.csv",
        "target": REPO / "test-data/generated-10m/target.csv",
        "compare": ["sku", "amount", "region"],
        "rows": 10_000_000,
    },
]


def _budget(source: Path, target: Path, compare_cols: list[str], rows: int) -> int:
    sb, tb = source.stat().st_size, target.stat().st_size
    budget = plan_workload_budget(
        source_bytes=sb,
        target_bytes=tb,
        compare_column_count=len(compare_cols),
        cpu_cores=8,
        memory_budget_bytes=10 * 1024**3,
        target_duration_seconds=60,
        requested_chunk_rows=500_000,
        requested_partition_buckets=512,
        requested_max_workers=4,
        requested_sub_partition_buckets=1,
        source_row_estimate=rows,
        target_row_estimate=rows,
        identity_column_count=1,
        inline_native_spill=True,
    )
    return budget.chunk_rows


def bench_native_spill(source: Path, compare_cols: list[str], chunk_rows: int) -> dict:
    import pegasus_native as nat

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "source"
        t0 = time.perf_counter()
        result = nat.spill_mmap_file(
            str(source),
            str(out),
            "||",
            True,
            0,
            chunk_rows,
            ["id"],
            compare_cols,
            512,
            False,
        )
        elapsed = time.perf_counter() - t0
    rows = int(result["rows"])
    mb = source.stat().st_size / (1024 * 1024)
    return {
        "rows": rows,
        "seconds": round(elapsed, 2),
        "mb_per_s": round(mb / max(elapsed, 1e-9), 2),
        "chunk_rows": chunk_rows,
    }


def bench_full_reconcile(
    source: Path,
    target: Path,
    compare_cols: list[str],
    chunk_rows: int,
) -> dict:
    cfg = TabularPipelineConfig(
        chunk_rows=chunk_rows,
        partition_count=512,
        enable_in_memory_reconcile=False,
        auto_in_memory_max_bytes=0,
        force_disk_spill=True,
        enable_column_drilldown=False,
        fingerprint_algorithm="xxhash64",
        fingerprint_only_spill=True,
        use_arrow_ipc_spill=True,
        enable_merkle_fast_path=False,
        partition_reconcile_workers=4,
    )
    src_ad = FileDelimitedAdapter(source, delimiter="||")
    tgt_ad = FileDelimitedAdapter(target, delimiter="||")
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        result = TabularReconciliationPipeline(
            src_ad,
            tgt_ad,
            identity_columns=["id"],
            compare_columns=compare_cols,
            config=cfg,
        ).run(workspace=Path(td))
    elapsed = time.perf_counter() - t0
    timings = result.extra_stats.get("timings") or {}
    total_mb = (source.stat().st_size + target.stat().st_size) / (1024 * 1024)
    return {
        "rows": result.source_row_count,
        "seconds": round(elapsed, 2),
        "mb_per_s": round(total_mb / max(elapsed, 1e-9), 2),
        "path": result.extra_stats.get("path"),
        "matching": result.matching_count,
        "changed": result.changed_count,
        "missing": result.missing_count,
        "extra": result.extra_count,
        "serialization_s": timings.get("serialization_seconds"),
        "reconcile_s": timings.get("partition_reconciliation_seconds"),
        "chunk_rows": chunk_rows,
    }


def main() -> None:
    print("native_extension:", native_extension_available())
    results: dict[str, dict] = {}
    for fx in FIXTURES:
        if not fx["source"].is_file() or not fx["target"].is_file():
            print(f"skip {fx['label']}: fixture missing")
            continue
        chunk_rows = _budget(fx["source"], fx["target"], fx["compare"], fx["rows"])
        label = fx["label"]
        print(f"\n=== {label} (chunk_rows={chunk_rows}) ===")
        spill = bench_native_spill(fx["source"], fx["compare"], chunk_rows)
        print("native_spill:", json.dumps(spill))
        full = bench_full_reconcile(fx["source"], fx["target"], fx["compare"], chunk_rows)
        print("full_pipeline:", json.dumps(full))
        results[label] = {"native_spill": spill, "full_pipeline": full}
    out_path = REPO / "pegasus-backend/benchmark_native_scale.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
