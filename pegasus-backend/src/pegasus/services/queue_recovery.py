# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T16:00:00Z
# --- END GENERATED FILE METADATA ---

"""Recover validation jobs after API/worker container restarts."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.services.validation_paths import validation_jobs_root

logger = logging.getLogger(__name__)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(dumps_bytes(payload, indent=False))
    tmp.replace(path)


def recover_orphaned_jobs(settings: Settings) -> tuple[int, int]:
    """Re-queue orphaned jobs and fail stale running jobs. Returns (requeued, failed)."""
    root = validation_jobs_root(settings)
    if not root.is_dir():
        return 0, 0

    requeued = 0
    failed = 0
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        status_path = entry / "status.json"
        if not status_path.is_file():
            continue
        try:
            job_id = uuid.UUID(entry.name)
        except ValueError:
            continue
        try:
            st = loads_str(status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(st, dict):
            continue
        status_val = str(st.get("status") or "").lower()
        if status_val == "running":
            _atomic_write_json(
                status_path,
                {
                    "status": "failed",
                    "phase": "failed",
                    "message": "Worker interrupted (container restart or OOM); re-submit if needed",
                    "error": "Worker interrupted (container restart or OOM)",
                    "error_log": "validation_errors.log",
                    "progress": {"failed_at_epoch_s": time.time(), "recovered": True},
                },
            )
            failed += 1
            logger.warning("Marked stale running job %s as failed after recovery", job_id)
        elif status_val == "queued":
            requeued += 1
            logger.info("Found orphaned queued job %s for re-enqueue", job_id)

    return requeued, failed


def collect_orphaned_queued_job_dirs(settings: Settings) -> list[tuple[uuid.UUID, Path]]:
    """Return (job_id, job_dir) for queued jobs on disk (for in-memory queue recovery)."""
    root = validation_jobs_root(settings)
    out: list[tuple[uuid.UUID, Path]] = []
    if not root.is_dir():
        return out
    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        status_path = entry / "status.json"
        meta_path = entry / "meta.json"
        if not status_path.is_file() or not meta_path.is_file():
            continue
        try:
            job_id = uuid.UUID(entry.name)
            st = loads_str(status_path.read_text(encoding="utf-8"))
            if isinstance(st, dict) and str(st.get("status") or "").lower() == "queued":
                out.append((job_id, entry.resolve()))
        except (OSError, ValueError, TypeError):
            continue
    out.sort(key=lambda t: t[1].stat().st_mtime)
    return out
