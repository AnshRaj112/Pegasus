# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T06:34:19Z
# --- END GENERATED FILE METADATA ---

"""Detect and materialize tabular leaf members inside nested archives."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.validation.file_detection.archive_extract import materialize_validation_path

_TABULAR_LEAF_SUFFIXES = (".csv", ".tsv", ".psv", ".txt", ".dat")


def is_tabular_leaf_path(path: str) -> bool:
    leaf = path.rstrip("/").split("/")[-1].lower()
    return any(leaf.endswith(suffix) for suffix in _TABULAR_LEAF_SUFFIXES)


def archive_sample_has_tabular_leaf(paths: list[str] | None) -> bool:
    if not paths:
        return False
    return any(is_tabular_leaf_path(path) for path in paths)


def deepest_tabular_leaf_path(paths: list[str]) -> str | None:
    candidates = [path for path in paths if is_tabular_leaf_path(path)]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.count("/"), len(path)))


def materialize_archive_tabular_leaf(
    archive_path: Path,
    *,
    settings: Settings,
    work_dir: Path | None = None,
) -> Path:
    """Extract the nested delimited leaf from a local archive file."""
    resolved = archive_path.resolve()
    if not resolved.is_file():
        raise ValueError(f"archive not found: {resolved}")
    root = work_dir or Path(tempfile.mkdtemp(prefix="pegasus-archive-leaf-"))
    root.mkdir(parents=True, exist_ok=True)
    leaf = materialize_validation_path(
        resolved,
        root,
        settings=settings,
        depth=0,
        force=True,
    )
    if leaf == resolved:
        raise ValueError(f"no tabular leaf found in archive {resolved.name}")
    return leaf


def materialize_gcs_archive_tabular_leaf(
    adapter: object,
    *,
    settings: Settings,
    work_dir: Path | None = None,
) -> Path:
    """Download a GCS archive and extract its nested tabular leaf."""
    root = work_dir or Path(tempfile.mkdtemp(prefix="pegasus-archive-leaf-"))
    root.mkdir(parents=True, exist_ok=True)
    max_bytes = int(settings.validation_archive_max_extract_bytes)
    materialize = getattr(adapter, "materialize_to_temp_file", None)
    if not callable(materialize):
        raise TypeError("expected GCS adapter with materialize_to_temp_file")
    archive_path = materialize(max_bytes=max_bytes)
    return materialize_archive_tabular_leaf(
        archive_path,
        settings=settings,
        work_dir=root / "nested",
    )


def cleanup_work_dir(work_dir: Path | None) -> None:
    if work_dir is not None and work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
