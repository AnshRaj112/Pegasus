# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-19T09:47:48Z
# --- END GENERATED FILE METADATA ---

"""Server-side directory listing for the local-path file picker."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException, status

from pegasus.core.config import Settings
from pegasus.core.local_paths import (
    default_browse_path,
    default_browse_path_for_ui,
    resolve_local_path_on_disk,
    to_display_path,
)
from pegasus.schemas.validation import LocalBrowseEntry, LocalBrowseResponse

_LOCAL_BROWSE_MAX_ENTRIES = 5000


def require_local_path_access(settings: Settings) -> None:
    if not settings.validation_allow_local_paths:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Local path validation is disabled (set PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS=true).",
        )


def resolve_local_csv_path(raw: str, settings: Settings) -> Path:
    """Resolve *raw* to an absolute file path on the server (when local paths are enabled)."""
    require_local_path_access(settings)
    return resolve_local_path_on_disk(raw, settings, must_be_file=True)


def resolve_local_dir_for_browse(raw: str, settings: Settings) -> Path:
    """Resolve *raw* to an absolute directory (for GET /validate/local/browse)."""
    require_local_path_access(settings)
    return resolve_local_path_on_disk(raw, settings, must_be_dir=True)


def _browse_parent_path(current: Path) -> Path | None:
    parent = current.parent
    if parent == current:
        return None
    return parent


def build_local_browse_response(directory: Path, settings: Settings) -> LocalBrowseResponse:
    """List *directory* (already resolved)."""
    parent = _browse_parent_path(directory)
    rows: list[tuple[bool, str, Path, str]] = []
    truncated = False
    try:
        with os.scandir(directory) as it:
            for entry in it:
                try:
                    child = Path(entry.path).resolve(strict=False)
                except OSError:
                    continue
                display_name = entry.name
                is_dir = child.is_dir()
                if not is_dir and not child.is_file():
                    continue
                rows.append((not is_dir, display_name.lower(), child, display_name))
    except OSError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cannot read directory: {exc}",
        ) from exc

    rows.sort(key=lambda t: (t[0], t[1]))
    if len(rows) > _LOCAL_BROWSE_MAX_ENTRIES:
        truncated = True
        rows = rows[:_LOCAL_BROWSE_MAX_ENTRIES]

    entries = [
        LocalBrowseEntry(
            name=display_name,
            path=to_display_path(p, settings),
            is_dir=p.is_dir(),
        )
        for _, _, p, display_name in rows
    ]
    return LocalBrowseResponse(
        path=to_display_path(directory, settings),
        parent_path=to_display_path(parent, settings) if parent is not None else None,
        entries=entries,
        truncated=truncated,
    )


__all__ = (
    "build_local_browse_response",
    "default_browse_path",
    "default_browse_path_for_ui",
    "require_local_path_access",
    "resolve_local_csv_path",
    "resolve_local_dir_for_browse",
)
