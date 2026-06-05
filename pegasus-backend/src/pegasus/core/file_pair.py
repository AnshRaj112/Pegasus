# --- BEGIN GENERATED FILE METADATA ---
<<<<<<< HEAD
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
=======
# Authors: github-actions[bot]
# Last edited: 2026-06-05T09:31:09Z
>>>>>>> 94051c3720b8bad458bdf77183420f7b053658d8
# --- END GENERATED FILE METADATA ---

"""Stable keys for grouping validation history by source/target file pair."""

from __future__ import annotations

import hashlib
from pathlib import Path


def normalize_validation_path(raw: str | None) -> str | None:
    """Resolve and normalize a path string for stable pair keys."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        return str(Path(text).expanduser().resolve())
    except OSError:
        return text


def compute_file_pair_key(
    source: str | None,
    target: str | None,
    *,
    normalize_paths: bool = True,
) -> str | None:
    """Return a hex digest identifying the same source+target pair across runs."""
    if not source or not target:
        return None
    if normalize_paths:
        source = normalize_validation_path(source) or source.strip()
        target = normalize_validation_path(target) or target.strip()
    else:
        source = source.strip()
        target = target.strip()
    payload = f"{source}\0{target}".encode()
    return hashlib.sha256(payload).hexdigest()
