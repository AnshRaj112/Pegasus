# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:46:02Z
# --- END GENERATED FILE METADATA ---

"""Subprocess / pool entrypoint: run one validation job from files under *job_dir*."""

from __future__ import annotations

import json
import logging
import shutil
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from pegasus.core.config import get_settings
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.schemas.validation import ColumnMapping, ValidationTestMode
from pegasus.services.exceptions import format_validation_job_error
from pegasus.services.validation_service import ValidationRunResult, ValidationService
from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.lifecycle_profiler import get_active_profiler, lifecycle_job, lifecycle_span
from pegasus.validation.resource_profiler import (
    JobResourceProfiler,
    log_resource_snapshot_summary,
    write_resource_profile_artifacts,
)

logger = logging.getLogger(__name__)

_COLUMNAR_FORMATS = frozenset({"parquet", "orc", "avro"})


def _write_json(path: Path, obj: object, *, indent: bool = False) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(dumps_bytes(obj, indent=indent))
    tmp.replace(path)


def _load_json(path: Path) -> dict[str, object]:
    return loads_str(path.read_text(encoding="utf-8"))


def _normalize_summary(summary: dict[str, int]) -> dict[str, int]:
    """Map pipeline summary keys to API mismatch type keys."""
    from pegasus.api.v1.mismatch_sample import normalize_mismatch_summary

    return normalize_mismatch_summary(summary)


def _merge_summary_counts(*summaries: dict[str, int]) -> dict[str, int]:
    merged = {
        MismatchType.MISSING_IN_TARGET.value: 0,
        MismatchType.EXTRA_IN_TARGET.value: 0,
        MismatchType.VALUE_MISMATCH.value: 0,
    }
    for summary in summaries:
        normalized = _normalize_summary(dict(summary))
        for key in merged:
            merged[key] = max(merged[key], int(normalized.get(key, 0)))
    return merged


def _resolve_job_mismatch_artifact(
    job_dir: Path,
    result: ValidationRunResult,
    artifact: Path | None,
) -> Path | None:
    export_path = job_dir / "mismatches.ndjson"
    if artifact is not None and artifact.is_file():
        try:
            artifact.resolve().relative_to(job_dir.resolve())
        except ValueError:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact, export_path)
            return export_path
        return artifact

    mismatches = result.report.mismatches
    if mismatches.is_empty():
        return None

    export_path.parent.mkdir(parents=True, exist_ok=True)
    mismatches.write_ndjson(export_path)
    logger.info("Exported in-memory mismatch report to %s rows=%d", export_path, mismatches.height)
    return export_path


def _artifact_lacks_cell_detail(path: Path) -> bool:
    """True when NDJSON value_mismatch rows have no column-level source/target values."""
    try:
        with path.open(encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("mismatch_type") != MismatchType.VALUE_MISMATCH.value:
                    continue
                if row.get("column_name") and (
                    row.get("source_value") not in (None, "")
                    or row.get("target_value") not in (None, "")
                ):
                    return False
                detail = row.get("row_detail")
                if isinstance(detail, str) and detail.strip():
                    try:
                        detail = json.loads(detail)
                    except json.JSONDecodeError:
                        detail = None
                if isinstance(detail, dict):
                    for side in ("source_record", "target_record"):
                        rec = detail.get(side)
                        if isinstance(rec, dict) and any(
                            k != "uid" for k in rec
                        ):
                            return False
                return True
    except (OSError, json.JSONDecodeError):
        return True
    return False


def _compare_policy_for_export(
    compare_columns: list[str],
    column_mappings: list[ColumnMapping],
) -> Any:
    from pegasus.validation.comparators.policy import ComparePolicy

    scanned: set[str] = set()
    for mapping in column_mappings:
        mode = (mapping.compare_mode or "auto").lower()
        if mode == "structured":
            scanned.add(mapping.source_column.strip())
    return ComparePolicy.from_mappings(compare_columns, column_mappings, scanned_complex=scanned)


def _cleanup_partial(job_dir: Path) -> None:
    for name in ("mismatches.ndjson", "result.json"):
        p = job_dir / name
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


def _configure_file_logging(job_dir: Path) -> None:
    log_path = job_dir / "worker.log"
    root = logging.getLogger()
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(sh)
    root.setLevel(logging.INFO)


def run_job_directory(job_dir: Path) -> int:
    """Execute validation for *job_dir*; return Unix-style exit code (0 success)."""
    job_dir = job_dir.resolve()
    _configure_file_logging(job_dir)
    status_path = job_dir / "status.json"
    meta_path = job_dir / "meta.json"

    def _fail(msg: str) -> int:
        _write_json(
            status_path,
            {
                "status": "failed",
                "phase": "failed",
                "message": "Validation worker failed",
                "error": msg,
                "progress": {"failed_at_epoch_s": time.time()},
            },
        )
        return 1

    if not meta_path.is_file():
        return _fail("job_dir missing meta.json")

    meta = _load_json(meta_path)
    uid_column = str(meta.get("uid_column") or "")
    delimiter = str(meta.get("delimiter") or "auto")
    column_mappings = [ColumnMapping.model_validate(m) for m in list(meta.get("column_mappings") or [])]
    has_header = bool(meta.get("has_header", True))
    header_leading_rows = int(meta.get("header_leading_rows") or 0)
    test_mode = str(meta.get("test_mode") or "full").strip().lower()
    file_format = str(meta.get("file_format") or "csv").lower()

    from pegasus.validation.cloud_input import delimited_input_from_meta

    source_input = delimited_input_from_meta(
        meta,
        side="source",
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=header_leading_rows,
    )
    target_input = delimited_input_from_meta(
        meta,
        side="target",
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=header_leading_rows,
    )
    uses_cloud = bool(meta.get("source_cloud") or meta.get("target_cloud"))

    if source_input is None or target_input is None:
        sp = meta.get("source_path")
        tp = meta.get("target_path")
        if sp and tp:
            src = Path(str(sp)).resolve()
            tgt = Path(str(tp)).resolve()
        else:
            src = job_dir / "source.csv"
            tgt = job_dir / "target.csv"
        if not src.is_file() or not tgt.is_file():
            return _fail("Validation input files not found")
    elif uses_cloud:
        src = source_input.adapter
        tgt = target_input.adapter
    else:
        src = source_input.adapter.path
        tgt = target_input.adapter.path
        if not src.is_file() or not tgt.is_file():
            return _fail("Validation input files not found")

    def _on_term(_sig: int, _frame: object) -> None:
        logger.warning("validation worker received signal; writing failed status")
        _fail("interrupted")
        sys.exit(1)

    signal.signal(signal.SIGTERM, _on_term)

    lifecycle_path = job_dir / "lifecycle_timings.json"
    prior_epochs: dict[str, float] = {}
    if lifecycle_path.is_file():
        try:
            prior = loads_str(lifecycle_path.read_text(encoding="utf-8"))
            raw_epochs = prior.get("epochs") if isinstance(prior, dict) else None
            if isinstance(raw_epochs, dict):
                for key, value in raw_epochs.items():
                    if isinstance(value, (int, float)):
                        prior_epochs[str(key)] = float(value)
        except (OSError, ValueError, TypeError):
            prior_epochs = {}

    try:
        with lifecycle_job(job_dir) as lifecycle:
            if prior_epochs.get("http_request_start_epoch_s") is not None:
                lifecycle.http_request_start_epoch_s = prior_epochs["http_request_start_epoch_s"]
            if prior_epochs.get("job_enqueued_epoch_s") is not None:
                lifecycle.job_enqueued_epoch_s = prior_epochs["job_enqueued_epoch_s"]
            lifecycle.mark_worker_started()
            return _run_job_body(
                job_dir=job_dir,
                meta=meta,
                meta_path=meta_path,
                status_path=status_path,
                uid_column=uid_column,
                delimiter=delimiter,
                column_mappings=column_mappings,
                has_header=has_header,
                header_leading_rows=header_leading_rows,
                test_mode=test_mode,
                file_format=file_format,
                source_input=source_input,
                target_input=target_input,
                uses_cloud=uses_cloud,
                src=src,
                tgt=tgt,
                lifecycle=lifecycle,
            )
    except Exception as exc:
        err_msg = format_validation_job_error(exc)
        logger.exception("validation job failed: %s", err_msg)
        report_path = job_dir / "resource_profile_report.md"
        if report_path.is_file():
            logger.info(
                "Resource footprint report for failed job %s written to %s",
                job_dir.name,
                report_path,
            )
        _write_json(
            status_path,
            {
                "status": "failed",
                "phase": "failed",
                "message": err_msg,
                "error": err_msg,
                "traceback": traceback.format_exc(),
                "progress": {"failed_at_epoch_s": time.time()},
            },
        )
        _cleanup_partial(job_dir)
        return 1


def _run_job_body(
    *,
    job_dir: Path,
    meta: dict[str, object],
    meta_path: Path,
    status_path: Path,
    uid_column: str,
    delimiter: str,
    column_mappings: list[ColumnMapping],
    has_header: bool,
    header_leading_rows: int,
    test_mode: str,
    file_format: str,
    source_input: object,
    target_input: object,
    uses_cloud: bool,
    src: object,
    tgt: object,
    lifecycle: object,
) -> int:
    job_id = job_dir.name
    resource_profiler = JobResourceProfiler(job_dir=job_dir)
    before = resource_profiler.capture_before()
    log_resource_snapshot_summary(before, phase="before", job_id=job_id)

    try:
        start = time.time()
        _write_json(
            status_path,
            {
                "status": "running",
                "phase": "initializing",
                "message": "Worker started, loading settings",
                "progress": {"started_at_epoch_s": start},
            },
        )
        with lifecycle_span("Worker Init (pre-validation)"):
            settings = get_settings()
            service = ValidationService(settings=settings)
        progress_interval = float(settings.validation_progress_status_interval_seconds or 2.5)
        last_emit = 0.0
        last_stage_emit = 0.0
        progress_seq = 0

        def _progress_cb(event: dict[str, Any]) -> None:
            nonlocal last_emit, last_stage_emit, progress_seq
            now = time.time()
            is_stage = event.get("phase") == "stage"
            is_terminal = event.get("percent") in {100, 99}
            stage_payload = event.get("stage")
            stage_name = (
                stage_payload.get("name")
                if isinstance(stage_payload, dict)
                else str(stage_payload) if stage_payload is not None else None
            )
            is_total_stage = stage_name == "Total"
            is_live = event.get("live") is True or str(event.get("phase") or "") in {
                "partitioning",
                "reconciling",
            }
            live_interval = min(progress_interval, 1.0)
            if is_stage:
                if (
                    not is_total_stage
                    and not is_terminal
                    and now - last_stage_emit < progress_interval
                ):
                    return
                last_stage_emit = now
            elif not is_terminal:
                interval = live_interval if is_live else progress_interval
                if now - last_emit < interval:
                    return
            last_emit = now
            progress_seq += 1
            progress: dict[str, Any] = {
                "started_at_epoch_s": start,
                "progress_seq": progress_seq,
                "percent": float(event.get("percent")) if event.get("percent") is not None else None,
                **(event.get("progress") if isinstance(event.get("progress"), dict) else {}),
            }
            if stage_payload is not None:
                progress["stage"] = stage_payload
            during_sample = resource_profiler.maybe_capture_during()
            if during_sample is not None:
                log_resource_snapshot_summary(during_sample, phase="during", job_id=job_id)
            _write_json(
                status_path,
                {
                    "status": "running",
                    "phase": str(event.get("phase") or "validating"),
                    "message": str(event.get("message") or "Running reconciliation"),
                    "progress": progress,
                },
            )

        try:
            src_bytes = src.stat().st_size if isinstance(src, Path) else None
            tgt_bytes = tgt.stat().st_size if isinstance(tgt, Path) else None
        except OSError:
            src_bytes = tgt_bytes = None
        logger.info(
            "validation inputs src=%s tgt=%s src_bytes=%s tgt_bytes=%s delimiter=%r format=%s",
            src,
            tgt,
            src_bytes,
            tgt_bytes,
            delimiter,
            file_format,
        )

        raw_policy = meta.get("resource_policy")
        resource_policy = raw_policy if isinstance(raw_policy, dict) else None

        if test_mode == ValidationTestMode.LITMUS.value:
            result = service.validate_csv_litmus_sync(
                source_path=src,
                target_path=tgt,
                delimiter=delimiter,
            )
        elif file_format in _COLUMNAR_FORMATS:
            result = service.validate_columnar_pair_sync(
                src,
                tgt,
                uid_column=uid_column,
                file_format=file_format,
                artifact_export_parent=job_dir,
            )
        elif uses_cloud:
            result = service._validate_delimited_adapters_sync(  # noqa: SLF001
                src,
                tgt,
                uid_column,
                delimiter,
                column_mappings,
                source_label=str(meta.get("source_filename") or source_input.display_name),
                target_label=str(meta.get("target_filename") or target_input.display_name),
                artifact_export_parent=job_dir,
                progress_callback=_progress_cb,
                has_header=has_header,
                header_leading_rows=header_leading_rows,
                file_format=file_format,
                resource_policy=resource_policy,
            )
        else:
            result = service._validate_csv_pair_sync(  # noqa: SLF001
                src,
                tgt,
                uid_column,
                delimiter,
                column_mappings,
                artifact_export_parent=job_dir,
                progress_callback=_progress_cb,
                has_header=has_header,
                header_leading_rows=header_leading_rows,
                file_format=file_format,
                resource_policy=resource_policy,
            )

        end = time.time()
        validation_duration = end - start
        profiler = get_active_profiler()
        if profiler is not None:
            profiler.mark_worker_finished()
        with lifecycle_span("Mismatch Export"):
            artifact = result.mismatch_artifact_path or result.report.mismatch_artifact_path
            workspace = job_dir / "reconcile_workspace"
            export_path = job_dir / "mismatches.ndjson"
            if workspace.is_dir() and result.compared_columns:
                try:
                    from pegasus.validation.comparators.policy import compare_policy_context
                    from pegasus.validation.pipeline.mismatch_export import export_workspace_mismatches_ndjson

                    export_policy = _compare_policy_for_export(
                        list(result.compared_columns),
                        column_mappings,
                    )
                    sensitive_cols = {
                        m.source_column.strip()
                        for m in column_mappings
                        if m.is_sensitive
                    } or None
                    with compare_policy_context(export_policy):
                        export_stats = export_workspace_mismatches_ndjson(
                            workspace,
                            export_path,
                            compare_columns=list(result.compared_columns),
                            sensitive_columns=sensitive_cols,
                        )
                    if export_stats.total > 0 and export_path.is_file():
                        artifact = export_path
                        result.report.summary = _merge_summary_counts(
                            dict(result.report.summary),
                            export_stats.to_summary(),
                        )
                        logger.info(
                            "Exported %d mismatch rows from spill workspace to %s "
                            "(missing=%d extra=%d value=%d)",
                            export_stats.total,
                            export_path,
                            export_stats.missing_in_target,
                            export_stats.extra_in_target,
                            export_stats.value_mismatch,
                        )
                except Exception:
                    logger.exception("Failed to export mismatches from reconcile workspace")
            if artifact is not None and artifact.is_file() and _artifact_lacks_cell_detail(artifact):
                rich = _resolve_job_mismatch_artifact(job_dir, result, None)
                if rich is not None and rich.is_file() and not _artifact_lacks_cell_detail(rich):
                    artifact = rich
                    logger.info("Using in-memory mismatch export with column detail at %s", rich)
            if artifact is None or not artifact.is_file():
                artifact = _resolve_job_mismatch_artifact(job_dir, result, artifact)
            if artifact is not None and artifact.is_file():
                from pegasus.api.v1.mismatch_sample import reconcile_summary_with_artifact

                result.report.summary = reconcile_summary_with_artifact(
                    dict(result.report.summary),
                    artifact,
                )
        artifact_rel = None
        artifact_abs = None
        if artifact is not None and artifact.is_file():
            artifact_abs = str(artifact)
            try:
                artifact_rel = str(artifact.relative_to(job_dir))
            except ValueError:
                artifact_rel = None

        out = {
            "source_row_count": result.source_row_count,
            "target_row_count": result.target_row_count,
            "compared_column_count": result.compared_column_count,
            "compared_columns": result.compared_columns,
            "summary": _normalize_summary(dict(result.report.summary)),
            "mismatch_artifact_rel": artifact_rel,
            "mismatch_artifact_path": artifact_abs,
            "mapping_format_checks": result.mapping_format_checks,
            "footer_validation": result.footer_validation,
            "test_mode": result.test_mode,
            "litmus": result.litmus,
            "durations": {
                "upload_seconds": 0.0,
                "validation_seconds": validation_duration,
                "total_seconds": validation_duration,
            },
        }
        reconcile_path = (getattr(result, "pipeline_metadata", None) or {}).get("path")
        logger.info(
            "validation completed in %.2fs path=%s (source_rows=%d target_rows=%d mismatches=%d)",
            validation_duration,
            reconcile_path or "unknown",
            result.source_row_count,
            result.target_row_count,
            int(sum(_normalize_summary(dict(result.report.summary)).values())),
        )
        lifecycle_summary = None
        if profiler is not None:
            profiler.record("Job Finalization", wall_seconds=time.time() - end, accumulate=False)
            profiler.write_artifacts()
            lifecycle_summary = profiler.summarize()
            out["lifecycle"] = lifecycle_summary
        resource_profiler.capture_after()
        log_resource_snapshot_summary(resource_profiler.after, phase="after", job_id=job_id)
        write_resource_profile_artifacts(job_dir, resource_profiler.to_dict())
        with lifecycle_span("Result Serialization"):
            _write_json(job_dir / "result.json", out, indent=True)
        _write_json(
            status_path,
            {
                "status": "completed",
                "phase": "completed",
                "message": f"Validation finished successfully in {validation_duration:.2f}s",
                "progress": {
                    "started_at_epoch_s": start,
                    "completed_at_epoch_s": time.time(),
                    "source_row_count": result.source_row_count,
                    "target_row_count": result.target_row_count,
                    "total_mismatch_records": int(sum(_normalize_summary(dict(result.report.summary)).values())),
                    "validation_seconds": validation_duration,
                },
            },
        )
        return 0
    except Exception as exc:
        if resource_profiler.after is None:
            try:
                resource_profiler.capture_after()
                log_resource_snapshot_summary(resource_profiler.after, phase="after", job_id=job_id)
            except Exception:
                logger.debug("Could not capture after-resource snapshot on failure", exc_info=True)
        try:
            write_resource_profile_artifacts(job_dir, resource_profiler.to_dict())
        except Exception:
            logger.debug("Could not write resource profile artifacts on failure", exc_info=True)
        raise exc
    finally:
        if uses_cloud:
            from pegasus.validation.gcs_stream import clear_gcs_stream_sessions

            clear_gcs_stream_sessions()


def run_job_directory_str(job_dir: str) -> int:
    """Pool entrypoint (picklable) for :func:`run_job_directory`."""
    return run_job_directory(Path(job_dir))


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python -m pegasus.validation.job_worker <job_dir>", file=sys.stderr)
        return 2
    return run_job_directory(Path(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
