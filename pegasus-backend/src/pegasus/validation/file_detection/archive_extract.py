# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:57:27Z
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
_TABULAR_SUFFIXES = frozenset({".csv", ".tsv", ".txt", ".dat", ".json", ".ndjson"})


def materialize_validation_path(
    path: Path,
    work_dir: Path,
    *,
    settings: Settings,
    depth: int = 0,
) -> Path:
    """Return a path suitable for validation (decompress or extract first tabular member)."""
    if not settings.validation_auto_extract_archives:
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
        extracted = _extract_first_tabular_zip(path, work_dir, max_bytes)
        if extracted:
            return materialize_validation_path(extracted, work_dir, settings=settings, depth=depth + 1)
    if container == "tar":
        extracted = _extract_first_tabular_tar(path, work_dir, max_bytes)
        if extracted:
            return materialize_validation_path(extracted, work_dir, settings=settings, depth=depth + 1)

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


def _extract_first_tabular_zip(path: Path, work_dir: Path, max_bytes: int) -> Path | None:
    work_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "r") as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")][:MAX_ARCHIVE_ENTRIES]
        for name in sorted(names, key=lambda n: (Path(n).suffix.lower() not in _TABULAR_SUFFIXES, n)):
            suffix = Path(name).suffix.lower()
            if suffix not in _TABULAR_SUFFIXES:
                continue
            info = zf.getinfo(name)
            if info.file_size > max_bytes:
                continue
            out = work_dir / Path(name).name
            with zf.open(name) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            return out
    return None


def _extract_first_tabular_tar(path: Path, work_dir: Path, max_bytes: int) -> Path | None:
    work_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "r:*") as tf:
        members = [m for m in tf.getmembers() if m.isfile()][:MAX_ARCHIVE_ENTRIES]
        for member in sorted(members, key=lambda m: (Path(m.name).suffix.lower() not in _TABULAR_SUFFIXES, m.name)):
            suffix = Path(member.name).suffix.lower()
            if suffix not in _TABULAR_SUFFIXES:
                continue
            if member.size > max_bytes:
                continue
            out = work_dir / Path(member.name).name
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            with extracted, out.open("wb") as dst:
                shutil.copyfileobj(extracted, dst, length=1024 * 1024)
            return out
    return None
