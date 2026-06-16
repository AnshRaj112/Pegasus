#!/usr/bin/env python3
# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T10:16:15Z
# --- END GENERATED FILE METADATA ---

"""Benchmark 100M-row / 12-column validation (local fixture)."""

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
        "compare": ["sku", "amount", "region"],
        "budget_min": 120,
    },
    "100m-12cols": {
        "source": REPO / "test-data/generated-100m-12cols/source.csv",
        "target": REPO / "test-data/generated-100m-12cols/target.csv",
        "uid": "id",
        "delimiter": "||",
        "compare": [
            "sku", "amount", "region", "attr4", "attr5", "attr6",
            "attr7", "attr8", "attr9", "attr10", "attr11",
        ],
        "budget_min": 600,
    },
}


def run_fixture(label: str, fx: dict) -> dict:
    source = fx["source"]
    target = fx["target"]
    if not source.is_file() or not target.is_file():
        return {"label": label, "skipped": True, "reason": "fixture missing"}

    settings = Settings(
        validation_enable_in_memory_reconcile=False,
        validation_tabular_enable_column_drilldown=False,
        validation_enable_content_digest_precheck=False,
        validation_partition_reconcile_workers=0,
        validation_target_duration_seconds=fx["budget_min"],
        validation_reconciliation_chunk_rows=500_000,
        validation_memory_budget_bytes=12 * 1024**3,
    )
    service = ValidationService(settings=settings)
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
        )
        elapsed = time.perf_counter() - t0

    total_mb = (source.stat().st_size + target.stat().st_size) / (1024**2)
    meta = result.pipeline_metadata or {}
    timings = meta.get("timings") or {}
    return {
        "label": label,
        "skipped": False,
        "native_extension": native_extension_available(),
        "seconds": round(elapsed, 2),
        "budget_minutes": fx["budget_min"] / 60,
        "under_budget": elapsed <= fx["budget_min"],
        "mb_per_s": round(total_mb / max(elapsed, 1e-9), 2),
        "source_rows": result.source_row_count,
        "target_rows": result.target_row_count,
        "path": meta.get("path"),
        "partition_buckets": meta.get("partition_buckets"),
        "chunk_rows": meta.get("chunk_rows"),
        "reconcile_workers": meta.get("reconcile_workers"),
        "timings": {
            k: timings.get(k)
            for k in (
                "source_partition_seconds",
                "target_partition_seconds",
                "partition_reconciliation_seconds",
                "total_seconds",
            )
            if timings.get(k) is not None
        },
        "mismatches": int(sum((result.report.summary or {}).values())),
    }


def main() -> None:
    labels = sys.argv[1:] or ["10m"]
    results = {}
    for label in labels:
        if label not in FIXTURES:
            print(f"unknown fixture: {label}")
            continue
        print(f"\n=== Benchmark {label} ===")
        print(f"native_extension: {native_extension_available()}")
        row = run_fixture(label, FIXTURES[label])
        results[label] = row
        print(json.dumps(row, indent=2))
        if row.get("skipped"):
            continue
        status = "PASS" if row.get("under_budget") else "SLOW"
        print(f"{status}: {row['seconds']}s (budget {row['budget_minutes']} min)")

    out = REPO / "pegasus-backend" / "benchmark_100m_results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
