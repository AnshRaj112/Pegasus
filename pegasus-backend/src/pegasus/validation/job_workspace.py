# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Ephemeral OS-level /tmp workspaces for validation spill (always deleted)."""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from pegasus.core.json_util import dumps_bytes, loads_str

logger = logging.getLogger(__name__)

_WORKSPACE_ROOT_NAME = "pegasus_job_workspace"
_META_KEY = "ephemeral_workspace"


def workspace_root() -> Path:
    root = Path(tempfile.gettempdir()) / _WORKSPACE_ROOT_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def acquire_ephemeral_workspace(job_dir: Path, *, job_id: str | None = None) -> Path:
    """Create a unique spill directory under the OS temp folder and record it in meta.json."""
    job_dir = job_dir.resolve()
    label = job_id or job_dir.name
    path = Path(tempfile.mkdtemp(prefix=f"pegasus_ws_{label}_", dir=workspace_root()))
    meta_path = job_dir / "meta.json"
    try:
        meta: dict[str, object] = {}
        if meta_path.is_file():
            loaded = loads_str(meta_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                meta = loaded
        meta[_META_KEY] = str(path)
        meta_path.write_bytes(dumps_bytes(meta, indent=True))
    except OSError:
        logger.warning("Could not persist ephemeral workspace path to %s", meta_path, exc_info=True)
    logger.info("Acquired ephemeral validation workspace %s for job %s", path, label)
    return path


def read_ephemeral_workspace(job_dir: Path) -> Path | None:
    meta_path = job_dir / "meta.json"
    if not meta_path.is_file():
        return None
    try:
        meta = loads_str(meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            return None
        raw = meta.get(_META_KEY)
        if not raw:
            return None
        return Path(str(raw))
    except (OSError, ValueError, TypeError):
        return None


def release_ephemeral_workspace(workspace: Path | None) -> None:
    """Synchronously remove an ephemeral workspace directory (idempotent)."""
    if workspace is None:
        return
    path = Path(workspace)
    if not path.exists():
        return
    try:
        shutil.rmtree(path, ignore_errors=False)
        logger.info("Released ephemeral validation workspace %s", path)
    except OSError:
        logger.warning("Force-removing ephemeral workspace %s", path, exc_info=True)
        shutil.rmtree(path, ignore_errors=True)


def release_job_workspace(job_dir: Path) -> None:
    """Best-effort cleanup using meta.json (callable from parent after worker exit)."""
    release_ephemeral_workspace(read_ephemeral_workspace(job_dir))
    legacy = job_dir / "reconcile_workspace"
    if legacy.is_dir():
        try:
            shutil.rmtree(legacy, ignore_errors=False)
        except OSError:
            shutil.rmtree(legacy, ignore_errors=True)
