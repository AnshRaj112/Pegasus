# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T10:54:38Z
# --- END GENERATED FILE METADATA ---

"""Safe archive pair validation — metadata manifest diff and streaming byte digest (no decompress)."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import polars as pl
import xxhash

from pegasus.validation.comparators.models import (
    MISMATCH_REPORT_SCHEMA,
    MismatchReport,
    MismatchType,
    VALUE_MISMATCH_ROWS_SUMMARY_KEY,
    empty_mismatch_frame,
)
from pegasus.validation.file_detection.layers.container import MAX_ARCHIVE_ENTRIES
from pegasus.validation.file_format import is_archive_format, normalize_archive_format

_DIGEST_BLOCK_BYTES = 4 * 1024 * 1024
_ARCHIVE_UID = "archive"
_METADATA_COLUMNS = ("compressed_size", "uncompressed_size", "crc32", "compress_type")
_TAR_BLOCK = 512
MAX_ARCHIVE_NEST_DEPTH = 3
_NESTED_MEMBER_SUFFIXES: tuple[str, ...] = (".tar.gz", ".tgz", ".tar", ".zip", ".7z", ".rar")


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    path: str
    compressed_size: int
    uncompressed_size: int
    crc32: int | None
    compress_type: int | None
    mtime: int | None
    is_dir: bool


@dataclass(slots=True)
class ArchiveSide:
    """One side of an archive comparison (local path or GCS ref)."""

    local_path: Path | None
    gcs_ref: object | None
    size_bytes: int
    crc32c: str | None = None
    md5_hex: str | None = None
    archive_format: str = "zip"
    manifest_supported: bool = True
    warnings: list[str] | None = None


def stream_digest_hex_from_path(path: Path, *, chunk_bytes: int = _DIGEST_BLOCK_BYTES) -> str:
    """Return ``xxh64:…`` digest by streaming *path* in fixed-size blocks."""
    hasher = xxhash.xxh64()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_bytes)
            if not block:
                break
            hasher.update(block)
    return f"xxh64:{hasher.hexdigest()}"


def stream_digest_hex_from_chunks(chunks: Iterator[bytes]) -> str:
    hasher = xxhash.xxh64()
    for block in chunks:
        if block:
            hasher.update(block)
    return f"xxh64:{hasher.hexdigest()}"


def _normalize_entry_path(name: str) -> str:
    return name.replace("\\", "/").rstrip("/")


def _zip_entry_from_info(info: zipfile.ZipInfo) -> ArchiveEntry:
    is_dir = info.filename.endswith("/") or info.is_dir()
    return ArchiveEntry(
        path=_normalize_entry_path(info.filename),
        compressed_size=int(info.compress_size),
        uncompressed_size=int(info.file_size),
        crc32=int(info.CRC),
        compress_type=int(info.compress_type),
        mtime=None,
        is_dir=is_dir,
    )


def assert_archive_headers_safe(
    entries: list[ArchiveEntry],
    *,
    max_declared_bytes: int,
    max_compression_ratio: float,
) -> None:
    """Reject zip-bomb signatures using header metadata only."""
    total_declared = sum(e.uncompressed_size for e in entries if not e.is_dir)
    if total_declared > max_declared_bytes:
        raise ValueError(
            f"archive declared uncompressed size {total_declared} exceeds limit {max_declared_bytes}"
        )
    for entry in entries:
        if entry.is_dir:
            continue
        compressed = max(entry.compressed_size, 1)
        ratio = entry.uncompressed_size / compressed
        if ratio > max_compression_ratio:
            raise ValueError(
                f"archive entry {entry.path!r} compression ratio {ratio:.0f} exceeds "
                f"limit {max_compression_ratio:.0f}"
            )


def _join_archive_path(prefix: str, name: str) -> str:
    leaf = _normalize_entry_path(name)
    if not prefix:
        return leaf
    return f"{prefix.rstrip('/')}/{leaf}"


def _is_nested_archive_member(name: str) -> bool:
    low = name.lower().rstrip("/")
    return any(low.endswith(suffix) for suffix in _NESTED_MEMBER_SUFFIXES)


def _detect_nested_container(data: bytes, name: str) -> str | None:
    if len(data) >= 2 and data[:2] == b"PK":
        return "zip"
    low = name.lower()
    if low.endswith((".tar", ".tgz", ".tar.gz")):
        return "tar"
    if len(data) >= 262 and data[257:262].startswith(b"ustar"):
        return "tar"
    return None


def _entry_with_path(entry: ArchiveEntry, path: str) -> ArchiveEntry:
    return ArchiveEntry(
        path=path,
        compressed_size=entry.compressed_size,
        uncompressed_size=entry.uncompressed_size,
        crc32=entry.crc32,
        compress_type=entry.compress_type,
        mtime=entry.mtime,
        is_dir=entry.is_dir,
    )


def _zip_entry_with_path(info: zipfile.ZipInfo, path: str) -> ArchiveEntry:
    base = _zip_entry_from_info(info)
    return _entry_with_path(base, path)


def _read_zip_member_bytes(
    zf: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    max_nested_member_bytes: int,
    max_compression_ratio: float,
) -> bytes:
    if info.file_size > max_nested_member_bytes:
        raise ValueError(
            f"nested archive member {info.filename!r} size {info.file_size} exceeds "
            f"limit {max_nested_member_bytes}"
        )
    compressed = max(int(info.compress_size), 1)
    ratio = int(info.file_size) / compressed
    if ratio > max_compression_ratio:
        raise ValueError(
            f"nested archive member {info.filename!r} compression ratio {ratio:.0f} exceeds "
            f"limit {max_compression_ratio:.0f}"
        )
    with zf.open(info) as member:
        data = member.read(int(info.file_size) + 1)
    if len(data) > int(info.file_size):
        raise ValueError(f"nested archive member {info.filename!r} produced more bytes than declared")
    return data[: int(info.file_size)]


def _manifest_from_bytes(
    data: bytes,
    member_name: str,
    *,
    prefix: str,
    depth: int,
    max_nest_depth: int,
    max_nested_member_bytes: int,
    max_declared_bytes: int,
    max_compression_ratio: float,
) -> list[ArchiveEntry]:
    if depth >= max_nest_depth:
        return []
    container = _detect_nested_container(data, member_name)
    if container == "zip":
        with zipfile.ZipFile(BytesIO(data)) as inner:
            return _iter_zip_manifest_nested(
                inner,
                prefix=prefix,
                depth=depth,
                max_nest_depth=max_nest_depth,
                max_nested_member_bytes=max_nested_member_bytes,
                max_declared_bytes=max_declared_bytes,
                max_compression_ratio=max_compression_ratio,
            )
    if container == "tar":
        return iter_tar_manifest_nested_from_stream(
            BytesIO(data),
            prefix=prefix,
            depth=depth,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
        )
    return []


def _iter_zip_manifest_nested(
    zf: zipfile.ZipFile,
    *,
    prefix: str = "",
    depth: int = 0,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
    max_declared_bytes: int = 50 * 1024**3,
    max_compression_ratio: float = 1000.0,
    warnings: list[str] | None = None,
) -> list[ArchiveEntry]:
    entries: list[ArchiveEntry] = []
    warn = warnings if warnings is not None else []
    for info in zf.infolist():
        if len(entries) >= MAX_ARCHIVE_ENTRIES:
            warn.append("archive entry list truncated at max entries")
            break
        if info.is_dir() or info.filename.endswith("/"):
            continue
        full_path = _join_archive_path(prefix, info.filename)
        nested = (
            depth < max_nest_depth
            and _is_nested_archive_member(info.filename)
            and int(info.file_size) <= max_nested_member_bytes
        )
        if nested:
            try:
                payload = _read_zip_member_bytes(
                    zf,
                    info,
                    max_nested_member_bytes=max_nested_member_bytes,
                    max_compression_ratio=max_compression_ratio,
                )
                inner_prefix = f"{full_path}/"
                entries.extend(
                    _manifest_from_bytes(
                        payload,
                        info.filename,
                        prefix=inner_prefix,
                        depth=depth + 1,
                        max_nest_depth=max_nest_depth,
                        max_nested_member_bytes=max_nested_member_bytes,
                        max_declared_bytes=max_declared_bytes,
                        max_compression_ratio=max_compression_ratio,
                    )
                )
                continue
            except (OSError, ValueError, zipfile.BadZipFile) as exc:
                warn.append(f"could not expand nested zip member {full_path!r}: {exc}")
        elif _is_nested_archive_member(info.filename) and int(info.file_size) > max_nested_member_bytes:
            warn.append(f"nested member {full_path!r} skipped (exceeds nested size limit)")
        entries.append(_zip_entry_with_path(info, full_path))
    return entries


def iter_zip_manifest(path: Path) -> list[ArchiveEntry]:
    """List ZIP entries, expanding nested archives up to depth/size limits."""
    return iter_zip_manifest_nested(
        path,
        max_nest_depth=MAX_ARCHIVE_NEST_DEPTH,
        max_nested_member_bytes=64 * 1024 * 1024,
        max_declared_bytes=50 * 1024**3,
        max_compression_ratio=1000.0,
    )


def iter_zip_manifest_nested(
    path: Path,
    *,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
    max_declared_bytes: int = 50 * 1024**3,
    max_compression_ratio: float = 1000.0,
    warnings: list[str] | None = None,
) -> list[ArchiveEntry]:
    with zipfile.ZipFile(path, "r") as zf:
        entries = _iter_zip_manifest_nested(
            zf,
            depth=0,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            warnings=warnings,
        )
    assert_archive_headers_safe(
        entries,
        max_declared_bytes=max_declared_bytes,
        max_compression_ratio=max_compression_ratio,
    )
    return entries


def _is_tar_metadata_header(name: str, typeflag: bytes) -> bool:
    """Skip POSIX/GNU metadata records — sizes vary between writers."""
    if typeflag in (b"x", b"g"):
        return True
    if "@PaxHeader" in name:
        return True
    if name.startswith("GNU/"):
        return True
    return False


def _parse_tar_header(block: bytes) -> ArchiveEntry | None:
    if len(block) < 512 or block == b"\0" * 512:
        return None
    name_raw = block[0:100].split(b"\0", 1)[0]
    if not name_raw:
        return None
    try:
        name = name_raw.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        name = name_raw.decode("latin-1", errors="replace")
    size_oct = block[124:136].split(b"\0", 1)[0].strip()
    try:
        size = int(size_oct, 8) if size_oct else 0
    except ValueError:
        size = 0
    typeflag = block[156:157]
    is_dir = typeflag == b"5" or name.endswith("/")
    return ArchiveEntry(
        path=_normalize_entry_path(name),
        compressed_size=size,
        uncompressed_size=size,
        crc32=None,
        compress_type=None,
        mtime=None,
        is_dir=is_dir,
    )


def _skip_bytes(handle: BinaryIO, nbytes: int) -> None:
    """Advance a sequential stream without loading all skipped bytes into memory."""
    remaining = max(0, nbytes)
    chunk_size = 1024 * 1024
    while remaining > 0:
        block = handle.read(min(remaining, chunk_size))
        if not block:
            break
        remaining -= len(block)


def iter_tar_manifest_from_stream(
    handle: BinaryIO,
    *,
    prefix: str = "",
    depth: int = 0,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
    max_declared_bytes: int = 50 * 1024**3,
    max_compression_ratio: float = 1000.0,
    warnings: list[str] | None = None,
) -> list[ArchiveEntry]:
    """Walk plain TAR headers sequentially, expanding nested archive members."""
    return iter_tar_manifest_nested_from_stream(
        handle,
        prefix=prefix,
        depth=depth,
        max_nest_depth=max_nest_depth,
        max_nested_member_bytes=max_nested_member_bytes,
        max_declared_bytes=max_declared_bytes,
        max_compression_ratio=max_compression_ratio,
        warnings=warnings,
    )


def iter_tar_manifest_nested_from_stream(
    handle: BinaryIO,
    *,
    prefix: str = "",
    depth: int = 0,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
    max_declared_bytes: int = 50 * 1024**3,
    max_compression_ratio: float = 1000.0,
    warnings: list[str] | None = None,
) -> list[ArchiveEntry]:
    entries: list[ArchiveEntry] = []
    warn = warnings if warnings is not None else []
    while len(entries) < MAX_ARCHIVE_ENTRIES:
        header = handle.read(_TAR_BLOCK)
        if len(header) < _TAR_BLOCK:
            break
        entry = _parse_tar_header(header)
        if entry is None:
            break
        typeflag = header[156:157]
        if _is_tar_metadata_header(entry.path, typeflag):
            payload_bytes = (entry.uncompressed_size + _TAR_BLOCK - 1) // _TAR_BLOCK * _TAR_BLOCK
            if payload_bytes:
                _skip_bytes(handle, payload_bytes)
            continue
        if not entry.path or entry.path in {".", ""}:
            payload_bytes = (entry.uncompressed_size + _TAR_BLOCK - 1) // _TAR_BLOCK * _TAR_BLOCK
            if payload_bytes:
                _skip_bytes(handle, payload_bytes)
            continue

        full_path = _join_archive_path(prefix, entry.path)
        payload_size = int(entry.uncompressed_size)
        payload_padded = (payload_size + _TAR_BLOCK - 1) // _TAR_BLOCK * _TAR_BLOCK

        nested = (
            not entry.is_dir
            and depth < max_nest_depth
            and _is_nested_archive_member(entry.path)
            and payload_size <= max_nested_member_bytes
        )
        if nested and payload_size > 0:
            payload = handle.read(payload_size)
            if len(payload) < payload_size:
                warn.append(f"truncated nested tar member {full_path!r}")
            else:
                pad = payload_padded - payload_size
                if pad > 0:
                    _skip_bytes(handle, pad)
                try:
                    entries.extend(
                        _manifest_from_bytes(
                            payload,
                            entry.path,
                            prefix=f"{full_path}/",
                            depth=depth + 1,
                            max_nest_depth=max_nest_depth,
                            max_nested_member_bytes=max_nested_member_bytes,
                            max_declared_bytes=max_declared_bytes,
                            max_compression_ratio=max_compression_ratio,
                        )
                    )
                    continue
                except (OSError, ValueError, zipfile.BadZipFile) as exc:
                    warn.append(f"could not expand nested tar member {full_path!r}: {exc}")
        elif _is_nested_archive_member(entry.path) and payload_size > max_nested_member_bytes:
            warn.append(f"nested member {full_path!r} skipped (exceeds nested size limit)")

        entries.append(_entry_with_path(entry, full_path))
        if payload_padded:
            _skip_bytes(handle, payload_padded)
    return entries


def iter_tar_manifest(
    path: Path,
    *,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
    max_declared_bytes: int = 50 * 1024**3,
    max_compression_ratio: float = 1000.0,
    warnings: list[str] | None = None,
) -> list[ArchiveEntry]:
    with path.open("rb") as handle:
        entries = iter_tar_manifest_nested_from_stream(
            handle,
            depth=0,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            warnings=warnings,
        )
    assert_archive_headers_safe(
        entries,
        max_declared_bytes=max_declared_bytes,
        max_compression_ratio=max_compression_ratio,
    )
    return entries


def manifest_supported_for_format(archive_format: str, object_name: str = "") -> bool:
    fmt = normalize_archive_format(archive_format)
    lower = object_name.lower()
    if fmt == "zip":
        return True
    if fmt == "tar":
        if lower.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
            return False
        return True
    return False


def _entry_map(entries: list[ArchiveEntry]) -> dict[str, ArchiveEntry]:
    return {e.path: e for e in entries if e.path}


def _entry_detail(entry: ArchiveEntry | None) -> dict[str, object]:
    if entry is None:
        return {}
    return {k: v for k, v in asdict(entry).items() if v is not None}


def _metadata_mismatch_rows(
    src: ArchiveEntry,
    tgt: ArchiveEntry,
    *,
    uid: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for field in _METADATA_COLUMNS:
        src_val = getattr(src, field)
        tgt_val = getattr(tgt, field)
        if src_val != tgt_val:
            rows.append({
                "uid": uid,
                "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                "column_name": field,
                "source_value": str(src_val) if src_val is not None else None,
                "target_value": str(tgt_val) if tgt_val is not None else None,
                "row_detail": json.dumps(
                    {"source": _entry_detail(src), "target": _entry_detail(tgt)},
                    ensure_ascii=False,
                ),
            })
    return rows


def _build_match_frame(uids: list[str]) -> pl.DataFrame:
    if not uids:
        return empty_mismatch_frame()
    rows = [
        {
            "uid": uid,
            "mismatch_type": MismatchType.VALUE_MATCH.value,
            "column_name": None,
            "source_value": None,
            "target_value": None,
            "row_detail": None,
        }
        for uid in sorted(uids)[:50]
    ]
    return pl.DataFrame(rows, schema=MISMATCH_REPORT_SCHEMA)


def compare_archive_manifests(
    source_entries: list[ArchiveEntry],
    target_entries: list[ArchiveEntry],
) -> MismatchReport:
    src_map = _entry_map(source_entries)
    tgt_map = _entry_map(target_entries)
    mismatch_rows: list[dict[str, object]] = []
    value_mismatch_uids: set[str] = set()

    for path, src_entry in sorted(src_map.items()):
        tgt_entry = tgt_map.get(path)
        if tgt_entry is None:
            mismatch_rows.append({
                "uid": path,
                "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                "column_name": None,
                "source_value": None,
                "target_value": None,
                "row_detail": json.dumps({"source": _entry_detail(src_entry)}, ensure_ascii=False),
            })
            continue
        field_rows = _metadata_mismatch_rows(src_entry, tgt_entry, uid=path)
        if field_rows:
            mismatch_rows.extend(field_rows)
            value_mismatch_uids.add(path)

    for path, tgt_entry in sorted(tgt_map.items()):
        if path not in src_map:
            mismatch_rows.append({
                "uid": path,
                "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                "column_name": None,
                "source_value": None,
                "target_value": None,
                "row_detail": json.dumps({"target": _entry_detail(tgt_entry)}, ensure_ascii=False),
            })

    if mismatch_rows:
        frame = pl.DataFrame(mismatch_rows, schema=MISMATCH_REPORT_SCHEMA)
    else:
        frame = _build_match_frame(list(src_map.keys()))

    missing = sum(1 for r in mismatch_rows if r["mismatch_type"] == MismatchType.MISSING_IN_TARGET.value)
    extra = sum(1 for r in mismatch_rows if r["mismatch_type"] == MismatchType.EXTRA_IN_TARGET.value)
    summary = {
        MismatchType.MISSING_IN_TARGET.value: missing,
        MismatchType.EXTRA_IN_TARGET.value: extra,
        MismatchType.VALUE_MISMATCH.value: len(value_mismatch_uids),
        VALUE_MISMATCH_ROWS_SUMMARY_KEY: len(value_mismatch_uids),
    }
    return MismatchReport(mismatches=frame, summary=summary)


def _byte_identical_report(entry_count: int, *, method: str) -> MismatchReport:
    frame = _build_match_frame([_ARCHIVE_UID] if entry_count <= 0 else [])
    if frame.is_empty() and entry_count > 0:
        uids = [f"entry_{i}" for i in range(min(entry_count, 50))]
        frame = _build_match_frame(uids)
    summary = {
        MismatchType.MISSING_IN_TARGET.value: 0,
        MismatchType.EXTRA_IN_TARGET.value: 0,
        MismatchType.VALUE_MISMATCH.value: 0,
        VALUE_MISMATCH_ROWS_SUMMARY_KEY: 0,
    }
    report = MismatchReport(mismatches=frame, summary=summary)
    report.summary["precheck_method"] = method  # type: ignore[index]
    return report


def _byte_mismatch_report(
    *,
    source_digest: str,
    target_digest: str,
    source_size: int,
    target_size: int,
) -> MismatchReport:
    row = {
        "uid": _ARCHIVE_UID,
        "mismatch_type": MismatchType.VALUE_MISMATCH.value,
        "column_name": "content_digest",
        "source_value": source_digest,
        "target_value": target_digest,
        "row_detail": json.dumps(
            {
                "source_size_bytes": source_size,
                "target_size_bytes": target_size,
                "source_digest": source_digest,
                "target_digest": target_digest,
            },
            ensure_ascii=False,
        ),
    }
    frame = pl.DataFrame([row], schema=MISMATCH_REPORT_SCHEMA)
    summary = {
        MismatchType.MISSING_IN_TARGET.value: 0,
        MismatchType.EXTRA_IN_TARGET.value: 0,
        MismatchType.VALUE_MISMATCH.value: 1,
        VALUE_MISMATCH_ROWS_SUMMARY_KEY: 1,
    }
    return MismatchReport(mismatches=frame, summary=summary)


def _gcs_metadata_identical(source: ArchiveSide, target: ArchiveSide) -> bool:
    if source.size_bytes != target.size_bytes or source.size_bytes <= 0:
        return False
    if source.crc32c and target.crc32c and source.crc32c == target.crc32c:
        return True
    if source.md5_hex and target.md5_hex and source.md5_hex == target.md5_hex:
        return True
    return False


def _digest_for_side(side: ArchiveSide) -> str:
    if side.local_path is not None:
        return stream_digest_hex_from_path(side.local_path)
    if side.gcs_ref is not None:
        from pegasus.validation.gcs_object import GcsObjectRef
        from pegasus.validation.gcs_stream import get_gcs_stream_session

        ref = side.gcs_ref if isinstance(side.gcs_ref, GcsObjectRef) else side.gcs_ref._ref  # type: ignore[attr-defined]
        session = get_gcs_stream_session(ref)
        return stream_digest_hex_from_chunks(session.iter_chunks(chunk_size=_DIGEST_BLOCK_BYTES))
    raise ValueError("archive side has no readable source")


def _manifest_for_side(
    side: ArchiveSide,
    *,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
    max_declared_bytes: int = 50 * 1024**3,
    max_compression_ratio: float = 1000.0,
    warnings: list[str] | None = None,
) -> list[ArchiveEntry]:
    if not side.manifest_supported:
        return []
    fmt = normalize_archive_format(side.archive_format)
    warn = warnings if warnings is not None else []
    if side.local_path is not None:
        if fmt == "zip":
            return iter_zip_manifest_nested(
                side.local_path,
                max_nest_depth=max_nest_depth,
                max_nested_member_bytes=max_nested_member_bytes,
                max_declared_bytes=max_declared_bytes,
                max_compression_ratio=max_compression_ratio,
                warnings=warn,
            )
        return iter_tar_manifest(
            side.local_path,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            warnings=warn,
        )
    if side.gcs_ref is not None:
        from pegasus.validation.archive_gcs import load_gcs_archive_manifest

        return load_gcs_archive_manifest(
            side.gcs_ref,
            archive_format=fmt,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            warnings=warn,
        )
    return []


def archive_side_from_path(path: Path, *, archive_format: str, object_name: str = "") -> ArchiveSide:
    resolved = path.resolve()
    name = object_name or resolved.name
    return ArchiveSide(
        local_path=resolved,
        gcs_ref=None,
        size_bytes=resolved.stat().st_size,
        archive_format=archive_format,
        manifest_supported=manifest_supported_for_format(archive_format, name),
    )


def archive_side_from_gcs_adapter(adapter: object, *, archive_format: str, object_name: str = "") -> ArchiveSide:
    adapter.warm_metadata()  # type: ignore[attr-defined]
    name = object_name or getattr(adapter, "path", Path("archive")).name
    return ArchiveSide(
        local_path=None,
        gcs_ref=adapter,
        size_bytes=int(adapter.get_size_bytes()),  # type: ignore[attr-defined]
        crc32c=getattr(adapter, "_crc32c", None),
        md5_hex=getattr(adapter, "_md5_hex", None),
        archive_format=archive_format,
        manifest_supported=manifest_supported_for_format(archive_format, name),
    )


def profile_archive_entries(
    side: ArchiveSide,
    *,
    max_declared_bytes: int,
    max_compression_ratio: float,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
) -> tuple[int, list[str], list[str]]:
    """Return (entry_count, sample_names, warnings)."""
    warnings: list[str] = list(side.warnings or [])
    if not side.manifest_supported:
        warnings.append("manifest comparison skipped (compressed archive wrapper)")
        return 0, [], warnings
    entries = _manifest_for_side(
        side,
        max_nest_depth=max_nest_depth,
        max_nested_member_bytes=max_nested_member_bytes,
        max_declared_bytes=max_declared_bytes,
        max_compression_ratio=max_compression_ratio,
        warnings=warnings,
    )
    names = [e.path for e in entries if not e.is_dir][:20]
    file_entries = [e for e in entries if not e.is_dir]
    if any("/" in n for n in names):
        warnings.append(f"expanded nested archive manifest (depth <= {max_nest_depth})")
    return len(file_entries), names, warnings


def validate_archive_pair(
    source: ArchiveSide,
    target: ArchiveSide,
    *,
    max_declared_bytes: int,
    max_compression_ratio: float,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
) -> MismatchReport:
    """Compare two archives: metadata precheck, streaming digest, then manifest diff."""
    if not is_archive_format(source.archive_format) or not is_archive_format(target.archive_format):
        raise ValueError("validate_archive_pair requires archive file_format")
    src_fmt = normalize_archive_format(source.archive_format)
    tgt_fmt = normalize_archive_format(target.archive_format)
    if src_fmt != tgt_fmt:
        raise ValueError(f"archive formats differ: source={src_fmt!r}, target={tgt_fmt!r}")

    if _gcs_metadata_identical(source, target):
        src_entries, _, _ = _safe_entry_count(
            source,
            max_declared_bytes,
            max_compression_ratio,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
        )
        return _byte_identical_report(src_entries, method="gcs_metadata")

    if source.size_bytes != target.size_bytes:
        pass
    else:
        src_digest = _digest_for_side(source)
        tgt_digest = _digest_for_side(target)
        if src_digest == tgt_digest:
            src_entries, _, _ = _safe_entry_count(
                source,
                max_declared_bytes,
                max_compression_ratio,
                max_nest_depth=max_nest_depth,
                max_nested_member_bytes=max_nested_member_bytes,
            )
            return _byte_identical_report(src_entries, method="content_digest")

    if source.manifest_supported and target.manifest_supported:
        src_warnings: list[str] = []
        tgt_warnings: list[str] = []
        src_entries = _manifest_for_side(
            source,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            warnings=src_warnings,
        )
        tgt_entries = _manifest_for_side(
            target,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            warnings=tgt_warnings,
        )
        assert_archive_headers_safe(
            src_entries,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
        )
        assert_archive_headers_safe(
            tgt_entries,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
        )
        return compare_archive_manifests(src_entries, tgt_entries)

    src_digest = _digest_for_side(source)
    tgt_digest = _digest_for_side(target)
    if src_digest == tgt_digest:
        return _byte_identical_report(0, method="content_digest")
    return _byte_mismatch_report(
        source_digest=src_digest,
        target_digest=tgt_digest,
        source_size=source.size_bytes,
        target_size=target.size_bytes,
    )


def _safe_entry_count(
    side: ArchiveSide,
    max_declared_bytes: int,
    max_compression_ratio: float,
    *,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
) -> tuple[int, list[str], list[str]]:
    try:
        return profile_archive_entries(
            side,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
        )
    except (OSError, ValueError, zipfile.BadZipFile):
        return 0, [], list(side.warnings or [])


class _GcsSeekableReader:
    """Minimal seekable reader over a GCS object for zipfile central-directory parsing."""

    __slots__ = ("_ref", "_size", "_pos", "_cache")

    def __init__(self, ref: object, size: int) -> None:
        self._ref = ref
        self._size = size
        self._pos = 0
        self._cache: dict[tuple[int, int], bytes] = {}

    def _fetch(self, start: int, length: int) -> bytes:
        end = min(self._size, start + length)
        if end <= start:
            return b""
        key = (start, end)
        if key in self._cache:
            return self._cache[key]
        from pegasus.validation.gcs_object import read_gcs_range

        data = read_gcs_range(self._ref, start=start, end=end - 1)
        if len(self._cache) < 32:
            self._cache[key] = data
        return data

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        elif whence == 2:
            self._pos = self._size + offset
        else:
            raise ValueError(f"invalid whence: {whence}")
        self._pos = max(0, min(self._pos, self._size))
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = self._size - self._pos
        if size <= 0 or self._pos >= self._size:
            return b""
        data = self._fetch(self._pos, size)
        self._pos += len(data)
        return data

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def close(self) -> None:
        return None


def zip_manifest_from_gcs_seekable(
    ref: object,
    size: int,
    *,
    max_nest_depth: int = MAX_ARCHIVE_NEST_DEPTH,
    max_nested_member_bytes: int = 64 * 1024 * 1024,
    max_declared_bytes: int = 50 * 1024**3,
    max_compression_ratio: float = 1000.0,
    warnings: list[str] | None = None,
) -> list[ArchiveEntry]:
    reader = _GcsSeekableReader(ref, size)
    with zipfile.ZipFile(reader) as zf:  # type: ignore[arg-type]
        entries = _iter_zip_manifest_nested(
            zf,
            depth=0,
            max_nest_depth=max_nest_depth,
            max_nested_member_bytes=max_nested_member_bytes,
            max_declared_bytes=max_declared_bytes,
            max_compression_ratio=max_compression_ratio,
            warnings=warnings,
        )
    assert_archive_headers_safe(
        entries,
        max_declared_bytes=max_declared_bytes,
        max_compression_ratio=max_compression_ratio,
    )
    return entries


def zip_manifest_from_suffix_bytes(suffix: bytes, total_size: int) -> list[ArchiveEntry]:
    """Parse ZIP central directory from a tail byte slice (local/GCS suffix fetch)."""
    reader = _SuffixZipReader(suffix, total_size)
    with zipfile.ZipFile(reader) as zf:  # type: ignore[arg-type]
        return [
            _zip_entry_from_info(info)
            for info in zf.infolist()[:MAX_ARCHIVE_ENTRIES]
        ]


class _SuffixZipReader:
    """Seekable view over object tail bytes for ZipFile EOCD parsing."""

    __slots__ = ("_suffix", "_total", "_offset", "_pos")

    def __init__(self, suffix: bytes, total_size: int) -> None:
        self._suffix = suffix
        self._total = total_size
        self._offset = total_size - len(suffix)
        self._pos = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        elif whence == 2:
            self._pos = self._total + offset
        else:
            raise ValueError(f"invalid whence: {whence}")
        self._pos = max(0, min(self._pos, self._total))
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, size: int = -1) -> bytes:
        if self._pos >= self._total:
            return b""
        if size < 0:
            size = self._total - self._pos
        start = self._pos - self._offset
        if start < 0:
            pad = b"\0" * (-start)
            start = 0
            chunk = self._suffix[start : start + max(0, size - len(pad))]
            out = pad + chunk
        else:
            out = self._suffix[start : start + size]
        self._pos += len(out)
        return out

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def close(self) -> None:
        return None
