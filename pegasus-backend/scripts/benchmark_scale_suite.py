#!/usr/bin/env python3
# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T11:10:12Z
# --- END GENERATED FILE METADATA ---

"""Benchmark 10M / 100M / 100M-12col validation with production-tuned settings."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pegasus-backend" / "src"))

from pegasus.core.config import Settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.readers.native_multichar import native_extension_available

FIXTURES = {
    "10m": {
        "source": REPO / "test-data/generated-10m/source.csv",
        "target": REPO / "test-data/generated-10m/target.csv",
        "uid": "id",
        "delimiter": "||",
        "budget_sec": 120,
    },
    "100m": {
        "source": REPO / "test-data/generated-100m/source.csv",
        "target": REPO / "test-data/generated-100m/target.csv",
        "uid": "id",
        "delimiter": "||",
        "budget_sec": 360,
    },
    "100m-12cols": {
        "source": REPO / "test-data/generated-100m-12cols/source.csv",
        "target": REPO / "test-data/generated-100m-12cols/target.csv",
        "uid": "id",
        "delimiter": "||",
        "budget_sec": 600,
    },
}


def production_settings(*, budget_sec: int) -> Settings:
    return Settings(
        validation_enable_in_memory_reconcile=False,
        validation_tabular_enable_column_drilldown=False,
        validation_enable_content_digest_precheck=False,
        validation_skip_artifact_report=True,
        validation_stream_mismatches_to_disk=False,
        validation_partition_reconcile_workers=0,
        validation_target_duration_seconds=budget_sec,
        validation_reconciliation_chunk_rows=1_000_000,
        validation_reconciliation_partition_buckets=256,
        validation_reconciliation_partition_wave_size=64,
        validation_partition_reconcile_use_processes=True,
        validation_memory_budget_bytes=12 * 1024**3,
    )


def run_fixture(label: str, fx: dict) -> dict:
    source = fx["source"]
    target = fx["target"]
    if not source.is_file() or not target.is_file():
        return {"label": label, "skipped": True, "reason": "fixture missing"}

    settings = production_settings(budget_sec=fx["budget_sec"])
    service = ValidationService(settings=settings)
    resource_policy = {
        "effective_threads_per_job": max(1, (os.cpu_count() or 4)),
        "memory_budget_bytes": settings.validation_memory_budget_bytes,
        "target_duration_seconds": settings.validation_target_duration_seconds,
    }
    total_mb = (source.stat().st_size + target.stat().st_size) / (1024**2)
    print(f"\n=== {label} ({total_mb:.0f} MB combined) ===", flush=True)
    print(f"native_extension={native_extension_available()} cpus={os.cpu_count()}", flush=True)

    with tempfile.TemporaryDirectory(prefix=f"pegasus-bench-{label}-") as td:
        os.environ["PEGASUS_VALIDATION_RECONCILIATION_TEMP_DIR"] = td
        t0 = time.perf_counter()
        result = service._validate_csv_pair_sync(  # noqa: SLF001
            source,
            target,
            uid_column=fx["uid"],
            delimiter=fx["delimiter"],
            column_mappings=None,
            artifact_export_parent=Path(td),
            has_header=True,
            header_leading_rows=0,
            file_format="csv",
            resource_policy=resource_policy,
        )
        elapsed = time.perf_counter() - t0

    meta = result.pipeline_metadata or {}
    timings = meta.get("timings") or {}
    row = {
        "label": label,
        "skipped": False,
        "native_extension": native_extension_available(),
        "seconds": round(elapsed, 2),
        "minutes": round(elapsed / 60, 2),
        "budget_sec": fx["budget_sec"],
        "under_budget": elapsed <= fx["budget_sec"],
        "mb_combined": round(total_mb, 1),
        "mb_per_s": round(total_mb / max(elapsed, 1e-9), 2),
        "source_rows": result.source_row_count,
        "target_rows": result.target_row_count,
        "path": meta.get("path"),
        "partition_buckets": meta.get("partition_buckets"),
        "chunk_rows": meta.get("chunk_rows"),
        "reconcile_workers": meta.get("reconcile_workers"),
        "timings": {k: timings[k] for k in timings if "seconds" in k},
        "mismatches": int(sum((result.report.summary or {}).values())),
    }
    status = "PASS" if row["under_budget"] else "SLOW"
    print(json.dumps(row, indent=2), flush=True)
    print(f"{status}: {row['minutes']} min ({row['seconds']}s)", flush=True)
    return row


def main() -> None:
    labels = sys.argv[1:] or ["10m", "100m", "100m-12cols"]
    results = {}
    for label in labels:
        if label not in FIXTURES:
            print(f"unknown fixture: {label}")
            continue
        results[label] = run_fixture(label, FIXTURES[label])

    out = REPO / "pegasus-backend" / "benchmark_scale_results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", flush=True)


if __name__ == "__main__":
    main()
