"""Subprocess / pool entrypoint: run one validation job from files under *job_dir*."""

from __future__ import annotations

import logging
import signal
import sys
import time
import traceback
import shutil
from pathlib import Path
from typing import Any

from pegasus.core.config import get_settings
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.schemas.validation import ColumnMapping
from pegasus.services.exceptions import format_validation_job_error
from pegasus.services.validation_service import ValidationRunResult, ValidationService
from pegasus.validation.reconciliation.memory_monitor import MemoryMonitor

logger = logging.getLogger(__name__)


def _write_json(path: Path, obj: object, *, indent: bool = False) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(dumps_bytes(obj, indent=indent))
    tmp.replace(path)


def _load_json(path: Path) -> dict[str, object]:
    return loads_str(path.read_text(encoding="utf-8"))


def _resolve_job_mismatch_artifact(
    job_dir: Path,
    result: ValidationRunResult,
    artifact: Path | None,
) -> Path | None:
    """Ensure mismatch rows are available under *job_dir* for API poll / detailed report.

    When ``validation_stream_mismatches_to_disk`` is false, reconciliation keeps mismatches
    in a Polars frame only; without this export the completed-job poll sees counts but no samples.
    """
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
    logger.info(
        "Exported in-memory mismatch report to %s rows=%d",
        export_path,
        mismatches.height,
    )
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
    validate_header_formats = bool(meta.get("validate_header_formats"))
    validate_footers = bool(meta.get("validate_footers"))
    footer_trailing_rows = int(meta.get("footer_trailing_rows") or 1)
    mem_iv = int(meta.get("memory_log_interval_seconds") or 0)
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

    monitor: MemoryMonitor | None = None
    if mem_iv > 0:
        monitor = MemoryMonitor(interval_sec=float(mem_iv))
        monitor.start()

    def _on_term(_sig: int, _frame: object) -> None:
        logger.warning("validation worker received signal; writing failed status")
        _fail("interrupted")
        if monitor:
            monitor.stop()
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
                    "message": str(event.get("message") or "Running external-memory reconciliation"),
                    "progress": {
                        "started_at_epoch_s": start,
                        "percent": float(event.get("percent")) if event.get("percent") is not None else None,
                        **(event.get("progress") if isinstance(event.get("progress"), dict) else {}),
                    },
                },
            )

        from pegasus.validation.fixed_width_meta import is_json_run, resolve_fixed_width_config

        json_run = is_json_run(
            file_format=str(meta.get("file_format") or "csv"),
            delimiter=str(meta.get("delimiter") or ""),
        )
        fixed_width_config = resolve_fixed_width_config(
            file_format=str(meta.get("file_format") or "csv"),
            delimiter=str(meta.get("delimiter") or ""),
            fixed_width_config=meta.get("fixed_width_config")
            if isinstance(meta.get("fixed_width_config"), dict)
            else None,
            column_mappings=list(meta.get("column_mappings") or []),
        )

        resource_policy = meta.get("resource_policy")
        if resource_policy is not None and not isinstance(resource_policy, dict):
            resource_policy = None

        if json_run:
            _write_json(
                status_path,
                {
                    "status": "running",
                    "phase": "validating",
                    "message": "Comparing JSON documents",
                    "progress": {"started_at_epoch_s": start},
                },
            )
            result = service.validate_json_pair_sync(
                src,
                tgt,
                artifact_export_parent=job_dir,
                progress_callback=_progress_cb,
            )
        elif fixed_width_config is not None:
            _write_json(
                status_path,
                {
                    "status": "running",
                    "phase": "validating",
                    "message": "Running streaming fixed-width validation",
                    "progress": {"started_at_epoch_s": start},
                },
            )
            result = service.validate_fixed_width_pair_sync(
                src,
                tgt,
                fixed_width_config,
                artifact_export_parent=job_dir,
                progress_callback=_progress_cb,
            )
        else:
            _write_json(
                status_path,
                {
                    "status": "running",
                    "phase": "validating",
                    "message": "Running external-memory reconciliation",
                    "progress": {"started_at_epoch_s": start},
                },
            )
            result = service._validate_csv_pair_sync(  # noqa: SLF001 — intentional worker entry
                src,
                tgt,
                uid_column,
                delimiter,
                column_mappings,
                artifact_export_parent=job_dir,
                progress_callback=_progress_cb,
                validate_header_formats=validate_header_formats,
                validate_footers=validate_footers,
                footer_trailing_rows=footer_trailing_rows,
                resource_policy=resource_policy,
            )
        end = time.time()
        validation_duration = end - start
        upload_duration = float(meta.get("upload_duration_seconds") or 0)
        
        logger.info(
            "Validation complete job_dir=%s upload=%.2fs validation=%.2fs total=%.2fs",
            job_dir.name, upload_duration, validation_duration, upload_duration + validation_duration
        )
        
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
            "summary": dict(result.report.summary),
            "mismatch_artifact_rel": artifact_rel,
            "mismatch_artifact_path": artifact_abs,
            "mapping_format_checks": result.mapping_format_checks,
            "footer_validation": result.footer_validation,
            "durations": {
                "upload_seconds": upload_duration,
                "validation_seconds": validation_duration,
                "total_seconds": upload_duration + validation_duration,
            }
        }
        _write_json(job_dir / "result.json", out, indent=True)
        _write_json(
            status_path,
            {
                "status": "completed",
                "phase": "completed",
                "message": "Validation finished successfully",
                "progress": {
                    "started_at_epoch_s": start,
                    "completed_at_epoch_s": time.time(),
                    "source_row_count": result.source_row_count,
                    "target_row_count": result.target_row_count,
                    "total_mismatch_records": int(sum(result.report.summary.values())),
                    "upload_seconds": upload_duration,
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
    finally:
        if monitor:
            monitor.stop()


def run_job_directory_str(job_dir: str) -> int:
    """Picklable pool entry: same as :func:`run_job_directory`."""
    return run_job_directory(Path(job_dir))


def main() -> int:
    if len(sys.argv) < 2:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        logger.error("usage: python -m pegasus.validation.job_worker <job_dir>")
        return 2
    return run_job_directory(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
