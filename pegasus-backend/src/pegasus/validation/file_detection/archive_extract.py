"""Bounded archive and compression materialization (no archive bombs)."""

from __future__ import annotations

import bz2
import gzip
import logging
import shutil
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MAX_ARCHIVE_DEPTH = 5
DEFAULT_MAX_ARCHIVE_ENTRIES = 1000
DEFAULT_MAX_EXTRACT_BYTES = 512 * 1024 * 1024  # 512 MiB per member
DEFAULT_MAX_EXTRACT_FILES = 32

_TABULAR_SUFFIXES = frozenset({
    ".csv",
    ".tsv",
    ".txt",
    ".dat",
    ".json",
    ".jsonl",
    ".ndjson",
    ".parquet",
    ".orc",
    ".avro",
    ".xlsx",
    ".xls",
})


class ArchiveExtractError(ValueError):
    """Archive could not be safely materialized."""


@dataclass(slots=True)
class MaterializedFile:
    """Resolved path ready for validation plus temp files to delete."""

    path: Path
    cleanup_paths: list[Path] = field(default_factory=list)
    extracted_from: str | None = None
    warnings: list[str] = field(default_factory=list)


def materialize_validation_path(
    path: Path,
    *,
    max_depth: int = DEFAULT_MAX_ARCHIVE_DEPTH,
    max_extract_bytes: int = DEFAULT_MAX_EXTRACT_BYTES,
    max_entries: int = DEFAULT_MAX_ARCHIVE_ENTRIES,
    work_dir: Path | None = None,
) -> MaterializedFile:
    """Decompress or extract *path* when needed; return a readable file path."""
    current = path.resolve()
    cleanup: list[Path] = []
    warnings: list[str] = []
    extracted_from: str | None = None
    depth = 0

    while depth < max_depth:
        suffix = current.suffix.lower()
        raw_head = current.read_bytes()[:16] if current.is_file() else b""

        if raw_head.startswith(b"\x1f\x8b") or suffix in {".gz", ".gzip"}:
            current, tmp = _decompress_gzip(current, max_bytes=max_extract_bytes, work_dir=work_dir)
            cleanup.append(tmp)
            warnings.append(f"decompressed gzip → {current.name}")
            depth += 1
            continue

        if raw_head.startswith(b"BZh") or suffix == ".bz2":
            current, tmp = _decompress_bz2(current, max_bytes=max_extract_bytes, work_dir=work_dir)
            cleanup.append(tmp)
            warnings.append(f"decompressed bzip2 → {current.name}")
            depth += 1
            continue

        if zipfile.is_zipfile(current):
            current, tmp_dir, inner_name = _extract_zip_member(
                current,
                max_bytes=max_extract_bytes,
                max_entries=max_entries,
                work_dir=work_dir,
            )
            cleanup.append(tmp_dir)
            extracted_from = inner_name
            warnings.append(f"extracted zip member {inner_name!r}")
            depth += 1
            continue

        if tarfile.is_tarfile(current):
            current, tmp_dir, inner_name = _extract_tar_member(
                current,
                max_bytes=max_extract_bytes,
                max_entries=max_entries,
                work_dir=work_dir,
            )
            cleanup.append(tmp_dir)
            extracted_from = inner_name
            warnings.append(f"extracted tar member {inner_name!r}")
            depth += 1
            continue

        break

    if depth >= max_depth:
        raise ArchiveExtractError(f"archive nesting exceeds max depth ({max_depth})")

    return MaterializedFile(
        path=current,
        cleanup_paths=cleanup,
        extracted_from=extracted_from,
        warnings=warnings,
    )


def _work_dir(base: Path | None) -> Path:
    if base is not None:
        base.mkdir(parents=True, exist_ok=True)
        return base
    return Path(tempfile.mkdtemp(prefix="pegasus_mat_"))


def _decompress_gzip(path: Path, *, max_bytes: int, work_dir: Path | None) -> tuple[Path, Path]:
    out_dir = _work_dir(work_dir)
    out = out_dir / f"{path.stem or 'payload'}.decompressed"
    total = 0
    with gzip.open(path, "rb") as src, out.open("wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ArchiveExtractError(f"gzip payload exceeds {max_bytes} bytes")
            dst.write(chunk)
    return out, out_dir


def _decompress_bz2(path: Path, *, max_bytes: int, work_dir: Path | None) -> tuple[Path, Path]:
    out_dir = _work_dir(work_dir)
    out = out_dir / f"{path.stem or 'payload'}.decompressed"
    data = bz2.decompress(path.read_bytes())
    if len(data) > max_bytes:
        raise ArchiveExtractError(f"bzip2 payload exceeds {max_bytes} bytes")
    out.write_bytes(data)
    return out, out_dir


def _pick_tabular_member(names: list[str]) -> str | None:
    candidates = [n for n in names if Path(n).suffix.lower() in _TABULAR_SUFFIXES and not n.endswith("/")]
    if not candidates:
        return None
    return sorted(candidates, key=lambda n: (n.count("/"), len(n)))[0]


def _extract_zip_member(
    path: Path,
    *,
    max_bytes: int,
    max_entries: int,
    work_dir: Path | None,
) -> tuple[Path, Path, str]:
    out_dir = _work_dir(work_dir)
    with zipfile.ZipFile(path, "r") as zf:
        names = [i.filename for i in zf.infolist() if not i.is_dir()][:max_entries]
        member = _pick_tabular_member(names)
        if member is None:
            raise ArchiveExtractError("zip archive has no tabular member")
        info = zf.getinfo(member)
        if info.file_size > max_bytes:
            raise ArchiveExtractError(f"zip member {member!r} exceeds size limit")
        target = out_dir / Path(member).name
        with zf.open(member) as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        return target, out_dir, member


def _extract_tar_member(
    path: Path,
    *,
    max_bytes: int,
    max_entries: int,
    work_dir: Path | None,
) -> tuple[Path, Path, str]:
    out_dir = _work_dir(work_dir)
    with tarfile.open(path, "r:*") as tf:
        members = [m for m in tf.getmembers() if m.isfile()][:max_entries]
        names = [m.name for m in members]
        pick = _pick_tabular_member(names)
        if pick is None:
            raise ArchiveExtractError("tar archive has no tabular member")
        member = tf.getmember(pick)
        if member.size > max_bytes:
            raise ArchiveExtractError(f"tar member {pick!r} exceeds size limit")
        extracted = tf.extractfile(member)
        if extracted is None:
            raise ArchiveExtractError(f"could not read tar member {pick!r}")
        target = out_dir / Path(pick).name
        with target.open("wb") as dst:
            shutil.copyfileobj(extracted, dst, length=1024 * 1024)
        return target, out_dir, pick
