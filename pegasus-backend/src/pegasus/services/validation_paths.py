# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T20:03:04+05:30
# --- END GENERATED FILE METADATA ---

"""Filesystem paths for validation jobs (no API/DB imports)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pegasus.core.config import Settings


def validation_jobs_root(settings: Settings) -> Path:
    raw = (settings.validation_jobs_directory or "").strip()
    base = Path(raw).expanduser() if raw else Path(tempfile.gettempdir()) / "pegasus_validation_jobs"
    base.mkdir(parents=True, exist_ok=True)
    return base
