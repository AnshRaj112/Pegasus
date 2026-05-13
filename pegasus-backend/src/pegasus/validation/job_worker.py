"""Subprocess / pool entrypoint: run one validation job from files under *job_dir*."""

from __future__ import annotations

import logging
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from pegasus.core.config import get_settings
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.services.validation_service import ValidationService
from pegasus.validation.reconciliation.memory_monitor import MemoryMonitor

logger = logging.getLogger(__name__)


def _write_json(path: Path, obj: object, *, indent: bool = False) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(dumps_bytes(obj, indent=indent))
    tmp.replace(path)


def _load_json(path: Path) -> dict[str, object]:
    return loads_str(path.read_text(encoding="utf-8"))


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
        return _fail("CSV inputs not found for validation job")

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
            artifact_export_parent=job_dir,
            progress_callback=_progress_cb,
        )
        end = time.time()
        validation_duration = end - start
        upload_duration = float(meta.get("upload_duration_seconds") or 0)
        
        logger.info(
            "Validation complete job_dir=%s upload=%.2fs validation=%.2fs total=%.2fs",
            job_dir.name, upload_duration, validation_duration, upload_duration + validation_duration
        )
        
        artifact = result.mismatch_artifact_path or result.report.mismatch_artifact_path
        out = {
            "source_row_count": result.source_row_count,
            "target_row_count": result.target_row_count,
            "compared_column_count": result.compared_column_count,
            "compared_columns": result.compared_columns,
            "summary": dict(result.report.summary),
            "mismatch_artifact_rel": artifact.name if artifact and artifact.is_file() else None,
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
        logger.exception("validation job failed: %s", exc)
        _write_json(
            status_path,
            {
                "status": "failed",
                "phase": "failed",
                "message": "Validation worker raised an exception",
                "error": repr(exc),
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
