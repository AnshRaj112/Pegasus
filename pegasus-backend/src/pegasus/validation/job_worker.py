# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T12:06:25+05:30
# --- END GENERATED FILE METADATA ---

"""Subprocess / pool entrypoint: run one validation job from files under *job_dir*."""

from __future__ import annotations

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
    if MismatchType.MISSING_IN_TARGET.value in summary:
        return dict(summary)
    return {
        MismatchType.MISSING_IN_TARGET.value: int(summary.get("missing", summary.get("missing_in_target", 0))),
        MismatchType.EXTRA_IN_TARGET.value: int(summary.get("extra", summary.get("extra_in_target", 0))),
        MismatchType.VALUE_MISMATCH.value: int(
            summary.get("changed", summary.get("value_mismatch", 0))
        ),
    }


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
        get_settings.cache_clear()
        settings = get_settings()
        service = ValidationService(settings=settings)
        last_emit = 0.0

        def _progress_cb(event: dict[str, Any]) -> None:
            nonlocal last_emit
            now = time.time()
            if now - last_emit < 2.5 and event.get("percent") not in {100, 99}:
                return
            last_emit = now
            _write_json(
                status_path,
                {
                    "status": "running",
                    "phase": str(event.get("phase") or "validating"),
                    "message": str(event.get("message") or "Running reconciliation"),
                    "progress": {
                        "started_at_epoch_s": start,
                        "percent": float(event.get("percent")) if event.get("percent") is not None else None,
                        **(event.get("progress") if isinstance(event.get("progress"), dict) else {}),
                    },
                },
            )

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
            )

        end = time.time()
        validation_duration = end - start
        artifact = result.mismatch_artifact_path or result.report.mismatch_artifact_path
        artifact = _resolve_job_mismatch_artifact(job_dir, result, artifact)
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
        logger.info(
            "validation completed in %.2fs (source_rows=%d target_rows=%d mismatches=%d)",
            validation_duration,
            result.source_row_count,
            result.target_row_count,
            int(sum(_normalize_summary(dict(result.report.summary)).values())),
        )
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
        err_msg = format_validation_job_error(exc)
        logger.exception("validation job failed: %s", err_msg)
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


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python -m pegasus.validation.job_worker <job_dir>", file=sys.stderr)
        return 2
    return run_job_directory(Path(args[0]))


if __name__ == "__main__":
    raise SystemExit(main())
