"""Execute multi-unit validation jobs (folder pairs, merge-then-validate)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from pegasus.core.config import Settings
from pegasus.core.json_util import dumps_bytes
from pegasus.schemas.validation import BatchFailureMode, ColumnMapping
from pegasus.services.exceptions import format_validation_job_error
from pegasus.services.validation_service import ValidationRunResult, ValidationService
from pegasus.validation.file_merge import merge_paths_for_format
from pegasus.validation.fixed_width_meta import is_json_run, resolve_fixed_width_config
from pegasus.validation.job_worker import _resolve_job_mismatch_artifact, _write_json


def run_batch_job_directory(
    job_dir: Path,
    *,
    settings: Settings,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> int:
    """Run a batch validation job; return Unix exit code."""
    from pegasus.core.json_util import loads_str

    job_dir = job_dir.resolve()
    meta_path = job_dir / "meta.json"
    status_path = job_dir / "status.json"
    meta = loads_str(meta_path.read_text(encoding="utf-8"))

    units = list(meta.get("units") or [])
    if not units:
        _write_json(
            status_path,
            {
                "status": "failed",
                "phase": "failed",
                "message": "Batch job missing units",
                "error": "meta.json has no units",
            },
        )
        return 1

    on_failure = str(meta.get("on_unit_failure") or BatchFailureMode.CONTINUE.value)
    stop_on_fail = on_failure == BatchFailureMode.STOP.value
    file_format = str(meta.get("file_format") or "csv")
    delimiter = str(meta.get("delimiter") or "auto")
    has_header = bool(meta.get("has_header", True))
    header_leading_rows = int(meta.get("header_leading_rows") or 0)
    validate_header_formats = bool(meta.get("validate_header_formats"))
    validate_footers = bool(meta.get("validate_footers"))
    footer_trailing_rows = int(meta.get("footer_trailing_rows") or 1)
    test_mode = str(meta.get("test_mode") or "full").strip().lower()
    uid_gte = str(meta.get("uid_gte")).strip() if meta.get("uid_gte") is not None else None
    resource_policy = meta.get("resource_policy")
    if resource_policy is not None and not isinstance(resource_policy, dict):
        resource_policy = None

    service = ValidationService(settings=settings)
    json_run = is_json_run(file_format=file_format, delimiter=delimiter)
    start = time.time()
    unit_results: list[dict[str, Any]] = []
    failed_count = 0
    skipped_count = 0
    passed_count = 0
    stop_triggered = False

    for idx, unit in enumerate(units):
        if stop_triggered:
            unit_results.append(_skipped_unit(unit))
            skipped_count += 1
            continue

        unit_id = str(unit.get("unit_id") or f"unit_{idx}")
        source_paths: list[Path] = []
        target_paths: list[Path] = []
        uid_column = str(unit.get("uid_column") or "id")
        column_mappings = [
            ColumnMapping.model_validate(m) for m in list(unit.get("column_mappings") or [])
        ]
        fixed_width_config = resolve_fixed_width_config(
            file_format=file_format,
            delimiter=delimiter,
            fixed_width_config=unit.get("fixed_width_config")
            if isinstance(unit.get("fixed_width_config"), dict)
            else None,
            column_mappings=[m.model_dump() for m in column_mappings],
        )

        if progress_callback is not None:
            progress_callback({
                "phase": "validating",
                "message": f"Validating unit {idx + 1} of {len(units)} ({unit_id})",
                "percent": round(100 * idx / max(len(units), 1), 1),
                "progress": {
                    "unit_index": idx,
                    "unit_id": unit_id,
                    "total_units": len(units),
                },
            })

        unit_dir = job_dir / "units" / unit_id
        unit_dir.mkdir(parents=True, exist_ok=True)
        try:
            cloud_bucket = meta.get("cloud_bucket")
            cloud_creds_json = meta.get("cloud_credentials_json")
            if cloud_bucket and cloud_creds_json:
                from pegasus.validation.gcs_browse import download_gcs_objects, parse_gcs_credentials_json

                creds_info = parse_gcs_credentials_json(str(cloud_creds_json))
                source_paths = download_gcs_objects(
                    bucket=str(cloud_bucket),
                    object_names=[str(p) for p in list(unit.get("source_paths") or [])],
                    credentials_info=creds_info,
                    project_id=meta.get("cloud_project_id"),
                    dest_dir=unit_dir / "cloud_source",
                )
                target_paths = download_gcs_objects(
                    bucket=str(cloud_bucket),
                    object_names=[str(p) for p in list(unit.get("target_paths") or [])],
                    credentials_info=creds_info,
                    project_id=meta.get("cloud_project_id"),
                    dest_dir=unit_dir / "cloud_target",
                )
            else:
                source_paths = [Path(str(p)).resolve() for p in list(unit.get("source_paths") or [])]
                target_paths = [Path(str(p)).resolve() for p in list(unit.get("target_paths") or [])]
                for side, paths in (("source", source_paths), ("target", target_paths)):
                    for p in paths:
                        if not p.is_file():
                            raise FileNotFoundError(f"{side} file not found: {p}")

            merged_source = merge_paths_for_format(
                source_paths,
                file_format=file_format,
                destination=unit_dir / f"merged_source{source_paths[0].suffix or '.dat'}",
                delimiter=delimiter if delimiter not in {"", "auto"} else ",",
                has_header=has_header,
            )
            merged_target = merge_paths_for_format(
                target_paths,
                file_format=file_format,
                destination=unit_dir / f"merged_target{target_paths[0].suffix or '.dat'}",
                delimiter=delimiter if delimiter not in {"", "auto"} else ",",
                has_header=has_header,
            )

            if json_run:
                result = service.validate_json_pair_sync(
                    merged_source,
                    merged_target,
                    artifact_export_parent=unit_dir,
                    progress_callback=progress_callback,
                )
            elif fixed_width_config is not None:
                result = service.validate_fixed_width_pair_sync(
                    merged_source,
                    merged_target,
                    fixed_width_config,
                    artifact_export_parent=unit_dir,
                    progress_callback=progress_callback,
                )
            elif test_mode == "litmus":
                result = service.validate_csv_litmus_sync(
                    source_path=merged_source,
                    target_path=merged_target,
                    uid_column=uid_column,
                    delimiter=delimiter,
                    has_header=has_header,
                    header_leading_rows=header_leading_rows,
                )
            else:
                result = service._validate_csv_pair_sync(  # noqa: SLF001
                    merged_source,
                    merged_target,
                    uid_column,
                    delimiter,
                    column_mappings,
                    artifact_export_parent=unit_dir,
                    progress_callback=progress_callback,
                    validate_header_formats=validate_header_formats,
                    validate_footers=validate_footers,
                    footer_trailing_rows=footer_trailing_rows,
                    has_header=has_header,
                    header_leading_rows=header_leading_rows,
                    uid_gte=uid_gte,
                    resource_policy=resource_policy,
                )

            artifact = result.mismatch_artifact_path or result.report.mismatch_artifact_path
            artifact = _resolve_job_mismatch_artifact(unit_dir, result, artifact)
            artifact_rel = None
            if artifact is not None and artifact.is_file():
                try:
                    artifact_rel = str(artifact.relative_to(unit_dir))
                except ValueError:
                    artifact_rel = None

            mismatch_total = int(sum(result.report.summary.values()))
            if mismatch_total == 0:
                passed_count += 1

            unit_payload = {
                "unit_id": unit_id,
                "source_paths": [str(p) for p in source_paths],
                "target_paths": [str(p) for p in target_paths],
                "status": "completed",
                "error": None,
                "result": {
                    "source_row_count": result.source_row_count,
                    "target_row_count": result.target_row_count,
                    "compared_column_count": result.compared_column_count,
                    "compared_columns": result.compared_columns,
                    "summary": dict(result.report.summary),
                    "mismatch_artifact_rel": artifact_rel,
                    "mapping_format_checks": result.mapping_format_checks,
                    "footer_validation": result.footer_validation,
                    "test_mode": result.test_mode,
                    "litmus": result.litmus,
                },
            }
            unit_results.append(unit_payload)
            (unit_dir / "result.json").write_bytes(dumps_bytes(unit_payload["result"], indent=True))
        except Exception as exc:
            err_msg = format_validation_job_error(exc)
            failed_count += 1
            unit_results.append({
                "unit_id": unit_id,
                "source_paths": [str(p) for p in source_paths],
                "target_paths": [str(p) for p in target_paths],
                "status": "failed",
                "error": err_msg,
                "result": None,
            })
            if stop_on_fail:
                stop_triggered = True

    completed_count = sum(1 for u in unit_results if u.get("status") == "completed")
    batch_payload = {
        "summary": {
            "total_units": len(units),
            "completed_units": completed_count,
            "failed_units": failed_count,
            "skipped_units": skipped_count,
            "passed_units": passed_count,
            "is_match": failed_count == 0 and skipped_count == 0 and passed_count == completed_count,
        },
        "units": unit_results,
        "on_unit_failure": on_failure,
        "durations": {
            "validation_seconds": time.time() - start,
            "total_seconds": time.time() - start,
        },
    }
    _write_json(job_dir / "batch_result.json", batch_payload, indent=True)

    if failed_count > 0 and stop_on_fail:
        _write_json(
            status_path,
            {
                "status": "failed",
                "phase": "failed",
                "message": f"Batch stopped after {failed_count} failed unit(s)",
                "error": unit_results[-1].get("error") if unit_results else "unit failed",
                "progress": {
                    "completed_units": completed_count,
                    "failed_units": failed_count,
                    "skipped_units": skipped_count,
                },
            },
        )
        return 1

    if failed_count > 0:
        _write_json(
            status_path,
            {
                "status": "completed",
                "phase": "completed",
                "message": f"Batch finished with {failed_count} failed unit(s)",
                "progress": {
                    "completed_units": completed_count,
                    "failed_units": failed_count,
                    "skipped_units": skipped_count,
                },
            },
        )
        return 0

    _write_json(
        status_path,
        {
            "status": "completed",
            "phase": "completed",
            "message": "Batch validation finished successfully",
            "progress": {
                "completed_units": completed_count,
                "failed_units": 0,
                "skipped_units": skipped_count,
            },
        },
    )
    return 0


def _skipped_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": str(unit.get("unit_id") or ""),
        "source_paths": [str(p) for p in list(unit.get("source_paths") or [])],
        "target_paths": [str(p) for p in list(unit.get("target_paths") or [])],
        "status": "skipped",
        "error": "Skipped because an earlier unit failed (stop on failure)",
        "result": None,
    }
