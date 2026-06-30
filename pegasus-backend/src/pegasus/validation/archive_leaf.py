# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:41:59Z
# --- END GENERATED FILE METADATA ---

"""Detect and materialize leaf members inside nested archives."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.validation.file_detection.archive_extract import materialize_validation_path
from pegasus.validation.file_detection.pipeline import detect_file

_TABULAR_LEAF_SUFFIXES = (".csv", ".tsv", ".psv", ".txt", ".dat")
_JSON_LEAF_SUFFIXES = (".json", ".ndjson")
_FIXED_WIDTH_LEAF_SUFFIXES = (".fw",)
_CHAIN_SEP = re.compile(r"\s*->\s*")


def _parse_format_chain(file_format: str | None) -> list[str]:
    if not file_format:
        return []
    return [
        segment.strip().lower().replace("_", "-")
        for segment in _CHAIN_SEP.split(file_format)
        if segment.strip()
    ]


def format_chain_has_json(file_format: str | None) -> bool:
    chain = _parse_format_chain(file_format)
    return any(seg in {"json", "ndjson"} for seg in chain)


def format_chain_has_fixed_width(file_format: str | None) -> bool:
    chain = _parse_format_chain(file_format)
    return any(seg in {"fixed-width", "fixedwidth"} for seg in chain)


def _leaf_basename(path: str) -> str:
    return path.rstrip("/").split("/")[-1].lower()


def is_tabular_leaf_path(path: str) -> bool:
    leaf = _leaf_basename(path)
    return any(leaf.endswith(suffix) for suffix in _TABULAR_LEAF_SUFFIXES)


def is_json_leaf_path(path: str) -> bool:
    leaf = _leaf_basename(path)
    return any(leaf.endswith(suffix) for suffix in _JSON_LEAF_SUFFIXES)


def is_fixed_width_leaf_path(path: str) -> bool:
    leaf = _leaf_basename(path)
    return any(leaf.endswith(suffix) for suffix in _FIXED_WIDTH_LEAF_SUFFIXES)


def archive_sample_has_json_leaf(
    paths: list[str] | None,
    *,
    file_format: str | None = None,
) -> bool:
    if format_chain_has_json(file_format):
        return True
    if not paths:
        return False
    return any(is_json_leaf_path(path) for path in paths)


def archive_sample_has_fixed_width_leaf(
    paths: list[str] | None,
    *,
    file_format: str | None = None,
) -> bool:
    if format_chain_has_fixed_width(file_format):
        return True
    if not paths:
        return False
    return any(is_fixed_width_leaf_path(path) for path in paths)


def archive_sample_may_be_fixed_width(
    paths: list[str] | None,
    *,
    file_format: str | None = None,
) -> bool:
    """True when manifest or format chain suggests a fixed-width inner member."""
    if archive_sample_has_fixed_width_leaf(paths, file_format=file_format):
        return True
    if format_chain_has_json(file_format):
        return False
    if not paths:
        return False
    return any(
        _leaf_basename(path).endswith((".txt", ".dat", ".fw"))
        for path in paths
    )


def archive_sample_has_tabular_leaf(
    paths: list[str] | None,
    *,
    file_format: str | None = None,
) -> bool:
    if format_chain_has_json(file_format) or format_chain_has_fixed_width(file_format):
        return False
    chain = _parse_format_chain(file_format)
    if any(seg in {"csv", "tsv", "psv", "delimited"} for seg in chain):
        return True
    if not paths:
        return False
    if any(_leaf_basename(path).endswith(suffix) for path in paths for suffix in (".csv", ".tsv", ".psv")):
        return True
    if any(
        _leaf_basename(path).endswith(suffix)
        for path in paths
        for suffix in (".txt", ".dat")
    ):
        return False
    return False


def deepest_json_leaf_path(paths: list[str]) -> str | None:
    candidates = [path for path in paths if is_json_leaf_path(path)]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.count("/"), len(path)))


def deepest_tabular_leaf_path(paths: list[str]) -> str | None:
    candidates = [path for path in paths if is_tabular_leaf_path(path)]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.count("/"), len(path)))


def _leaf_is_fixed_width(path: Path) -> bool:
    report = detect_file(path)
    suggested = (report.suggested_file_format or "").lower().replace("_", "-")
    structured = ""
    if report.structured_format:
        structured = (report.structured_format.detected_type or "").lower().replace("_", "-")
    return suggested == "fixed-width" or structured == "fixed-width"


def _materialize_archive_leaf(
    archive_path: Path,
    *,
    settings: Settings,
    work_dir: Path | None,
    leaf_filter: str,
    not_found_msg: str,
    verify_fixed_width: bool = False,
    reject_fixed_width: bool = False,
) -> Path:
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
        leaf_filter=leaf_filter,  # type: ignore[arg-type]
    )
    if leaf == resolved:
        raise ValueError(not_found_msg.format(name=resolved.name))
    if verify_fixed_width and not _leaf_is_fixed_width(leaf):
        raise ValueError(f"extracted leaf is not fixed-width: {leaf.name}")
    if reject_fixed_width and _leaf_is_fixed_width(leaf):
        raise ValueError(f"extracted leaf is fixed-width, not delimited tabular: {leaf.name}")
    return leaf


def materialize_archive_tabular_leaf(
    archive_path: Path,
    *,
    settings: Settings,
    work_dir: Path | None = None,
) -> Path:
    """Extract the nested delimited leaf from a local archive file."""
    return _materialize_archive_leaf(
        archive_path,
        settings=settings,
        work_dir=work_dir,
        leaf_filter="tabular",
        not_found_msg="no tabular leaf found in archive {name}",
        reject_fixed_width=True,
    )


def materialize_archive_json_leaf(
    archive_path: Path,
    *,
    settings: Settings,
    work_dir: Path | None = None,
) -> Path:
    """Extract the nested JSON leaf from a local archive file."""
    return _materialize_archive_leaf(
        archive_path,
        settings=settings,
        work_dir=work_dir,
        leaf_filter="json",
        not_found_msg="no JSON leaf found in archive {name}",
    )


def materialize_archive_fixed_width_leaf(
    archive_path: Path,
    *,
    settings: Settings,
    work_dir: Path | None = None,
) -> Path:
    """Extract the nested fixed-width leaf from a local archive file."""
    return _materialize_archive_leaf(
        archive_path,
        settings=settings,
        work_dir=work_dir,
        leaf_filter="fixed-width",
        not_found_msg="no fixed-width leaf found in archive {name}",
        verify_fixed_width=True,
    )


def _materialize_gcs_archive_leaf(
    adapter: object,
    *,
    settings: Settings,
    work_dir: Path | None,
    materialize_fn,
) -> Path:
    root = work_dir or Path(tempfile.mkdtemp(prefix="pegasus-archive-leaf-"))
    root.mkdir(parents=True, exist_ok=True)
    max_bytes = int(settings.validation_archive_max_extract_bytes)
    materialize = getattr(adapter, "materialize_to_temp_file", None)
    if not callable(materialize):
        raise TypeError("expected GCS adapter with materialize_to_temp_file")
    archive_path = materialize(max_bytes=max_bytes)
    return materialize_fn(
        archive_path,
        settings=settings,
        work_dir=root / "nested",
    )


def materialize_gcs_archive_tabular_leaf(
    adapter: object,
    *,
    settings: Settings,
    work_dir: Path | None = None,
) -> Path:
    """Download a GCS archive and extract its nested tabular leaf."""
    return _materialize_gcs_archive_leaf(
        adapter,
        settings=settings,
        work_dir=work_dir,
        materialize_fn=materialize_archive_tabular_leaf,
    )


def materialize_gcs_archive_json_leaf(
    adapter: object,
    *,
    settings: Settings,
    work_dir: Path | None = None,
) -> Path:
    """Download a GCS archive and extract its nested JSON leaf."""
    return _materialize_gcs_archive_leaf(
        adapter,
        settings=settings,
        work_dir=work_dir,
        materialize_fn=materialize_archive_json_leaf,
    )


def materialize_gcs_archive_fixed_width_leaf(
    adapter: object,
    *,
    settings: Settings,
    work_dir: Path | None = None,
) -> Path:
    """Download a GCS archive and extract its nested fixed-width leaf."""
    return _materialize_gcs_archive_leaf(
        adapter,
        settings=settings,
        work_dir=work_dir,
        materialize_fn=materialize_archive_fixed_width_leaf,
    )


def cleanup_work_dir(work_dir: Path | None) -> None:
    if work_dir is not None and work_dir.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
