# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:32:35Z
# --- END GENERATED FILE METADATA ---

"""Bounded archive decompression/extraction for validation materialization."""

from __future__ import annotations

import bz2
import gzip
import shutil
import tarfile
import zipfile
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.validation.file_detection.pipeline import detect_file

MAX_ARCHIVE_DEPTH = 3
MAX_ARCHIVE_ENTRIES = 1000
_TABULAR_SUFFIXES = frozenset({".csv", ".tsv", ".txt", ".dat", ".psv"})
_NESTED_ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar", ".zip", ".7z", ".rar")


def _is_nested_archive_name(name: str) -> bool:
    low = name.lower().rstrip("/")
    return any(low.endswith(suffix) for suffix in _NESTED_ARCHIVE_SUFFIXES)


def _member_priority(name: str) -> tuple[int, int, str]:
    """Prefer nested containers before tabular leaves at the same depth."""
    low = name.lower()
    suffix = Path(low).suffix.lower()
    is_tabular = suffix in _TABULAR_SUFFIXES
    is_nested = _is_nested_archive_name(low)
    return (0 if is_nested else 1, 0 if is_tabular else 1, low)


def materialize_validation_path(
    path: Path,
    work_dir: Path,
    *,
    settings: Settings,
    depth: int = 0,
    force: bool = False,
) -> Path:
    """Return a path suitable for validation (decompress or extract first tabular member)."""
    if not force and not settings.validation_auto_extract_archives:
        return path
    if depth > MAX_ARCHIVE_DEPTH:
        raise ValueError(f"archive nesting exceeds max depth {MAX_ARCHIVE_DEPTH}")

    report = detect_file(path)
    strategy = report.validation_strategy.detected_type if report.validation_strategy else ""
    compression = report.compression.detected_type if report.compression else "none"

    max_bytes = settings.validation_archive_max_extract_bytes

    if compression in {"gzip", "bzip2"} or (
        strategy == "decompress_first" and compression in {"gzip", "bzip2"}
    ):
        if compression == "bzip2":
            return _decompress_bz2(path, work_dir, max_bytes)
        return _decompress_gzip(path, work_dir, max_bytes)

    container = report.container.detected_type if report.container else "none"
    if container == "zip":
        extracted = _extract_next_zip_member(path, work_dir, max_bytes)
        if extracted:
            return materialize_validation_path(
                extracted,
                work_dir,
                settings=settings,
                depth=depth + 1,
                force=force,
            )
    if container == "tar":
        extracted = _extract_next_tar_member(path, work_dir, max_bytes)
        if extracted:
            return materialize_validation_path(
                extracted,
                work_dir,
                settings=settings,
                depth=depth + 1,
                force=force,
            )

    return path


def _decompress_gzip(path: Path, work_dir: Path, max_bytes: int) -> Path:
    out = work_dir / f"{path.stem}.decompressed"
    work_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    with gzip.open(path, "rb") as src, out.open("wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.unlink(missing_ok=True)
                raise ValueError(f"gzip decompress exceeds limit {max_bytes} bytes")
            dst.write(chunk)
    return out


def _decompress_bz2(path: Path, work_dir: Path, max_bytes: int) -> Path:
    out = work_dir / f"{path.stem}.decompressed"
    work_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    with bz2.open(path, "rb") as src, out.open("wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                out.unlink(missing_ok=True)
                raise ValueError(f"bzip2 decompress exceeds limit {max_bytes} bytes")
            dst.write(chunk)
    return out


def _extract_next_zip_member(path: Path, work_dir: Path, max_bytes: int) -> Path | None:
    work_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "r") as zf:
        names = [name for name in zf.namelist() if not name.endswith("/")][:MAX_ARCHIVE_ENTRIES]
        for name in sorted(names, key=_member_priority):
            suffix = Path(name).suffix.lower()
            info = zf.getinfo(name)
            if info.file_size > max_bytes:
                continue
            out = work_dir / Path(name).name
            if suffix in _TABULAR_SUFFIXES:
                with zf.open(name) as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                return out
            if _is_nested_archive_name(name):
                with zf.open(name) as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                return out
    return None


def _extract_next_tar_member(path: Path, work_dir: Path, max_bytes: int) -> Path | None:
    work_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "r:*") as tf:
        members = [member for member in tf.getmembers() if member.isfile()][:MAX_ARCHIVE_ENTRIES]
        for member in sorted(members, key=lambda item: _member_priority(item.name)):
            suffix = Path(member.name).suffix.lower()
            if member.size > max_bytes:
                continue
            out = work_dir / Path(member.name).name
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            with extracted, out.open("wb") as dst:
                shutil.copyfileobj(extracted, dst, length=1024 * 1024)
            if suffix in _TABULAR_SUFFIXES or _is_nested_archive_name(member.name):
                return out
    return None
