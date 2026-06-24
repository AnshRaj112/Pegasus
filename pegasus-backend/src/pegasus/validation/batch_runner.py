# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:01:15Z
# --- END GENERATED FILE METADATA ---

"""Sequential batch validation runner for multi-pair jobs."""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any

from pegasus.core.config import Settings
from pegasus.schemas.validation import BatchFailureMode, BatchUnitResult, BatchValidateSummary
from pegasus.services.validation_service import ValidationService

logger = logging.getLogger(__name__)


def _unit_paths(unit: dict[str, Any]) -> tuple[str, str]:
    source = unit.get("source_path") or (unit.get("source_paths") or [None])[0]
    target = unit.get("target_path") or (unit.get("target_paths") or [None])[0]
    if not source or not target:
        raise ValueError(f"batch unit {unit.get('unit_id')} missing source/target path")
    return str(source), str(target)


def run_batch_job(
    *,
    job_dir: Path,
    meta: dict[str, object],
    settings: Settings,
    status_path: Path,
    write_status: Any,
) -> int:
    """Run all batch units sequentially; return Unix exit code."""
    units = list(meta.get("batch_units") or [])
    if not units:
        return 1
    on_failure = str(meta.get("on_unit_failure") or BatchFailureMode.CONTINUE.value)
    delimiter = str(meta.get("delimiter") or "auto")
    has_header = bool(meta.get("has_header", True))
    header_leading_rows = int(meta.get("header_leading_rows") or 0)
    file_format = str(meta.get("file_format") or "csv").lower()
    service = ValidationService(settings)
    results_path = job_dir / "batch_results.jsonl"
    unit_outcomes: list[dict[str, object]] = []
    completed = failed = skipped = passed = 0
    t0 = time.time()

    for idx, raw_unit in enumerate(units):
        unit = dict(raw_unit) if isinstance(raw_unit, dict) else {}
        unit_id = str(unit.get("unit_id") or f"unit_{idx + 1}")
        write_status(
            status_path,
            {
                "status": "running",
                "phase": "batch",
                "message": f"Processing batch unit {idx + 1}/{len(units)}: {unit_id}",
                "progress": {
                    "completed_units": completed,
                    "total_units": len(units),
                    "current_unit": unit_id,
                },
            },
        )
        try:
            source_path, target_path = _unit_paths(unit)
            uid_column = str(unit.get("uid_column") or meta.get("uid_column") or "id")
            from pegasus.schemas.validation import ColumnMapping

            mappings = [
                ColumnMapping.model_validate(m)
                for m in list(unit.get("column_mappings") or meta.get("column_mappings") or [])
            ]
            unit_workspace = job_dir / f"unit_{unit_id}"
            unit_workspace.mkdir(parents=True, exist_ok=True)
            if file_format in {"parquet", "orc", "avro"}:
                result = service.validate_columnar_pair_sync(
                    Path(source_path),
                    Path(target_path),
                    uid_column=uid_column,
                    file_format=file_format,
                    artifact_export_parent=unit_workspace,
                )
            else:
                result = service._validate_csv_pair_sync(  # noqa: SLF001
                    Path(source_path),
                    Path(target_path),
                    uid_column,
                    delimiter,
                    mappings,
                    artifact_export_parent=unit_workspace,
                    has_header=has_header,
                    header_leading_rows=header_leading_rows,
                    file_format=file_format,
                )
            summary = dict(result.report.summary)
            total_mm = sum(int(v) for v in summary.values())
            if total_mm == 0:
                passed += 1
            completed += 1
            outcome: dict[str, object] = {
                "unit_id": unit_id,
                "source_paths": [source_path],
                "target_paths": [target_path],
                "status": "completed",
                "summary": summary,
                "source_row_count": result.source_row_count,
                "target_row_count": result.target_row_count,
            }
            unit_outcomes.append(outcome)
            with results_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(outcome, ensure_ascii=False) + "\n")
        except Exception as exc:
            failed += 1
            outcome = {
                "unit_id": unit_id,
                "status": "failed",
                "error": str(exc),
            }
            unit_outcomes.append(outcome)
            with results_path.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(outcome, ensure_ascii=False) + "\n")
            if on_failure == BatchFailureMode.STOP.value:
                skipped = len(units) - idx - 1
                break
        finally:
            ws = job_dir / f"unit_{unit_id}" / "reconcile_workspace"
            if ws.is_dir():
                shutil.rmtree(ws, ignore_errors=True)

    duration = time.time() - t0
    summary = BatchValidateSummary(
        total_units=len(units),
        completed_units=completed,
        failed_units=failed,
        skipped_units=skipped,
        passed_units=passed,
        is_match=failed == 0 and passed == completed and completed == len(units),
    )
    batch_payload = {
        "summary": summary.model_dump(),
        "units": unit_outcomes,
        "on_unit_failure": on_failure,
        "durations": {"total_seconds": duration, "validation_seconds": duration},
    }
    (job_dir / "batch_result.json").write_text(
        json.dumps(batch_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (job_dir / "result.json").write_text(
        json.dumps({"batch": True, **batch_payload}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_status(
        status_path,
        {
            "status": "completed" if failed == 0 else "completed",
            "phase": "completed",
            "message": f"Batch validation finished ({completed}/{len(units)} units)",
            "progress": {
                "completed_units": completed,
                "total_units": len(units),
                "failed_units": failed,
                "validation_seconds": duration,
            },
        },
    )
    return 0 if failed == 0 else 1
