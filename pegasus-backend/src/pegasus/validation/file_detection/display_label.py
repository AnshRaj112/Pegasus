# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:32:01Z
# --- END GENERATED FILE METADATA ---

"""Human-readable format labels from file detection reports (e.g. zip -> csv)."""

from __future__ import annotations

import bz2
import gzip
import shutil
import tarfile
import tempfile
import zipfile
import zlib
from pathlib import Path

from pegasus.validation.file_detection.pipeline import detect_file
from pegasus.validation.file_detection.types import FileDetectionReport
from pegasus.validation.file_format import is_ambiguous_tabular_suffix

MAX_ARCHIVE_DEPTH = 5
MAX_INNER_EXTRACT_BYTES = 64 * 1024 * 1024

_AMBIGUOUS_LEAF_SUFFIXES = frozenset({".txt", ".dat"})
_DELIMITED_LEAF_KINDS = frozenset({"csv", "tsv", "psv", "delimited"})

_CONTAINER_SUFFIXES: tuple[tuple[str, str], ...] = (
    (".tar.gz", "tar"),
    (".tgz", "tar"),
    (".tar", "tar"),
    (".zip", "zip"),
    (".7z", "7z"),
    (".rar", "rar"),
)
_COMPRESSION_SUFFIXES: tuple[tuple[str, str], ...] = (
    (".gz", "gzip"),
    (".bz2", "bzip2"),
    (".xz", "xz"),
    (".zst", "zstd"),
    (".lz4", "lz4"),
)
_LEAF_SUFFIXES: tuple[tuple[str, str], ...] = (
    (".parquet", "parquet"),
    (".pq", "parquet"),
    (".orc", "orc"),
    (".avro", "avro"),
    (".json", "json"),
    (".ndjson", "json"),
    (".csv", "csv"),
    (".tsv", "tsv"),
    (".psv", "psv"),
    (".xlsx", "excel"),
    (".xls", "excel"),
    (".png", "png"),
    (".jpg", "jpg"),
    (".jpeg", "jpeg"),
    (".gif", "gif"),
    (".webp", "webp"),
    (".bmp", "bmp"),
    (".pdf", "pdf"),
)


def _prefer_ambiguous_suffix_display(detected: str, display_name: str) -> str:
    """Keep .dat / .txt as the UI label when content sniff resolves to delimited tabular."""
    suffix = Path(display_name).suffix.lower()
    token = detected.lower().strip()
    if token in _DELIMITED_LEAF_KINDS:
        if suffix == ".dat":
            return "dat"
        if suffix == ".txt":
            return "txt"
    return detected


def build_format_display_label(
    report: FileDetectionReport,
    *,
    path: str | Path,
    object_name: str = "",
) -> str:
    """Return a display label such as ``zip -> csv`` or ``fixed-width``."""
    file_path = Path(path)
    display_name = object_name or file_path.name
    chain = _resolve_format_chain(file_path, report, display_name=display_name)
    if not chain:
        return "unknown"
    return " -> ".join(chain)


def _resolve_format_chain(
    path: Path,
    report: FileDetectionReport,
    *,
    display_name: str,
) -> list[str]:
    chain: list[str] = []
    compression = _stage_type(report.compression)
    container = _stage_type(report.container)

    if compression not in {"", "none"} and container in {"", "none"}:
        chain.append(compression)
        inner_report, inner_path = _inspect_decompressed(path, compression)
        if inner_report is not None:
            chain.extend(_resolve_format_chain(inner_path, inner_report, display_name=inner_path.name))
            return chain
        inner = _inner_suffix_chain_from_filename(display_name, skip_outer=compression)
        if inner:
            chain.extend(inner)
        else:
            chain.append(_leaf_type_from_report(report, display_name))
        return chain

    if container not in {"", "none"}:
        chain.append(container)
        inner_chain = _inspect_archive_inner(path, container, report)
        chain.extend(inner_chain)
        return chain

    return [_leaf_type_from_report(report, display_name)]


def _inspect_archive_inner(
    path: Path,
    container: str,
    report: FileDetectionReport,
) -> list[str]:
    if path.is_file() and path.stat().st_size > 0:
        try:
            if container == "zip":
                return _walk_zip_chain(path, depth=0)
            if container == "tar":
                return _walk_tar_chain(path, depth=0)
        except (OSError, zipfile.BadZipFile, tarfile.TarError):
            pass

    names = []
    if report.container and report.container.metadata:
        names = list(report.container.metadata.get("entry_names_sample") or [])
    if names:
        return _chain_from_entry_names(names)

    inner = _inner_suffix_chain_from_filename(path.name, skip_outer=container)
    return inner or ["unknown"]


def _inner_suffix_chain_from_filename(name: str, *, skip_outer: str | None = None) -> list[str]:
    chain = _suffix_chain_from_filename(name)
    if skip_outer and skip_outer in chain:
        idx = chain.index(skip_outer)
        chain = chain[:idx] + chain[idx + 1 :]
    return chain


def _compression_kind_from_name(name: str) -> str | None:
    lower = name.lower()
    for suffix, kind in _COMPRESSION_SUFFIXES:
        if lower.endswith(suffix):
            return kind
    return None


def _chain_from_extracted_path(
    path: Path,
    *,
    display_name: str,
    depth: int = 0,
) -> list[str]:
    """Resolve a format chain from an on-disk path (compression, archives, leaf)."""
    if depth >= MAX_ARCHIVE_DEPTH:
        return ["unknown"]
    report = detect_file(path)
    compression = _stage_type(report.compression)
    container = _stage_type(report.container)

    if compression not in {"", "none"} and container in {"", "none"}:
        inner_report, inner_path = _inspect_decompressed(path, compression)
        if inner_report is not None:
            return [compression, *_chain_from_extracted_path(
                inner_path, display_name=inner_path.name, depth=depth + 1,
            )]
        suffix_chain = _suffix_chain_from_filename(display_name)
        if suffix_chain:
            return [compression, *suffix_chain]
        return [compression, _leaf_type_from_report(report, display_name)]

    if container not in {"", "none"}:
        inner_chain = _inspect_archive_inner(path, container, report)
        return [container, *inner_chain]

    return [_leaf_type_from_report(report, display_name)]


def _member_name_fallback_chain(member: str) -> list[str]:
    """Infer inner chain from a member filename when extraction fails."""
    chain = _suffix_chain_from_filename(Path(member).name)
    if chain:
        return chain
    leaf = _leaf_type_from_member_name(member)
    return [leaf] if leaf != "unknown" else ["unknown"]


def _walk_zip_chain(path: Path, *, depth: int) -> list[str]:
    if depth >= MAX_ARCHIVE_DEPTH:
        return ["unknown"]
    with zipfile.ZipFile(path, "r") as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if not names:
            return ["unknown"]
        member = _pick_archive_member(names)
        return _resolve_member_leaf_from_zip(zf, member, depth=depth)
    return ["unknown"]


def _walk_tar_chain(path: Path, *, depth: int) -> list[str]:
    if depth >= MAX_ARCHIVE_DEPTH:
        return ["unknown"]
    with tarfile.open(path, "r:*") as tf:
        members = [m for m in tf.getmembers() if m.isfile()]
        if not members:
            return ["unknown"]
        member = _pick_archive_member([m.name for m in members])
        return _resolve_member_leaf_from_tar(tf, member, depth=depth)
    return ["unknown"]


def _inspect_decompressed(
    path: Path,
    compression: str,
) -> tuple[FileDetectionReport | None, Path]:
    try:
        extracted = _decompress_member(path, compression)
    except (OSError, EOFError, ValueError, zlib.error):
        return None, path
    if extracted is None:
        return None, path
    try:
        return detect_file(extracted), extracted
    except OSError:
        return None, path


def _decompress_member(path: Path, compression: str) -> Path | None:
    work_dir = Path(tempfile.mkdtemp(prefix="pegasus-fmt-"))
    out = work_dir / f"{path.stem}.inner"
    total = 0
    if compression == "gzip":
        opener = gzip.open
    elif compression == "bzip2":
        opener = bz2.open
    else:
        return None
    try:
        with opener(path, "rb") as src, out.open("wb") as dst:
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_INNER_EXTRACT_BYTES:
                    return None
                dst.write(chunk)
    except (OSError, EOFError, ValueError, zlib.error):
        return None
    return out


def _extract_zip_member(zf: zipfile.ZipFile, name: str) -> Path | None:
    try:
        info = zf.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_INNER_EXTRACT_BYTES:
        return None
    work_dir = Path(tempfile.mkdtemp(prefix="pegasus-fmt-"))
    out = work_dir / Path(name).name
    try:
        with zf.open(name) as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
    except OSError:
        return None
    return out


def _extract_tar_member(tf: tarfile.TarFile, name: str) -> Path | None:
    try:
        member = tf.getmember(name)
    except KeyError:
        return None
    if member.size > MAX_INNER_EXTRACT_BYTES:
        return None
    work_dir = Path(tempfile.mkdtemp(prefix="pegasus-fmt-"))
    out = work_dir / Path(name).name
    extracted = tf.extractfile(member)
    if extracted is None:
        return None
    try:
        with extracted, out.open("wb") as dst:
            shutil.copyfileobj(extracted, dst, length=1024 * 1024)
    except OSError:
        return None
    return out


def _requires_content_sniff(name: str) -> bool:
    return Path(name).suffix.lower() in _AMBIGUOUS_LEAF_SUFFIXES


def _resolve_member_leaf_from_zip(zf: zipfile.ZipFile, member: str, *, depth: int = 0) -> list[str]:
    extracted = _extract_zip_member(zf, member)
    if extracted is not None:
        return _chain_from_extracted_path(extracted, display_name=member, depth=depth + 1)
    return _member_name_fallback_chain(member)


def _resolve_member_leaf_from_tar(tf: tarfile.TarFile, member: str, *, depth: int = 0) -> list[str]:
    extracted = _extract_tar_member(tf, member)
    if extracted is not None:
        return _chain_from_extracted_path(extracted, display_name=member, depth=depth + 1)
    return _member_name_fallback_chain(member)


def _pick_archive_member(names: list[str]) -> str:
    def sort_key(name: str) -> tuple[int, int, str]:
        lower = name.lower()
        is_archive = int(_is_archive_member(lower))
        depth = lower.count("/")
        return (is_archive, -depth, lower)

    return sorted(names, key=sort_key)[0]


def _is_archive_member(name: str) -> bool:
    for suffix, _ in _CONTAINER_SUFFIXES:
        if name.endswith(suffix):
            return True
    for suffix, _ in _COMPRESSION_SUFFIXES:
        if name.endswith(suffix):
            return True
    return False


def _archive_kind_from_name(name: str) -> str:
    for suffix, kind in _CONTAINER_SUFFIXES:
        if name.endswith(suffix):
            return kind
    return "unknown"


def format_chain_from_archive_member_path(member_path: str, *, outer: str) -> list[str]:
    """Build format tokens from a nested virtual path (e.g. ``inner.tar/bundle.zip/data.csv``)."""
    normalized = member_path.replace("\\", "/").rstrip("/")
    if not normalized:
        return []
    parts = [part for part in normalized.split("/") if part]
    if not parts:
        return []
    chain: list[str] = [outer]
    for part in parts[:-1]:
        kind = _archive_kind_from_name(part.lower())
        if kind != "unknown":
            chain.append(kind)
    chain.append(_leaf_type_from_member_name(parts[-1]))
    return chain


def format_display_label_from_archive_members(
    member_paths: list[str],
    *,
    outer: str,
    object_name: str = "",
) -> str | None:
    """Render a nested archive display label from expanded manifest member paths."""
    candidates = [path for path in member_paths if path and not path.endswith("/")]
    if not candidates:
        inner = _inner_suffix_chain_from_filename(object_name, skip_outer=outer)
        if inner:
            return " -> ".join([outer, *inner])
        return None
    best = max(candidates, key=lambda path: (path.count("/"), len(path)))
    chain = format_chain_from_archive_member_path(best, outer=outer)
    if len(chain) < 2:
        return None
    return " -> ".join(chain)


def _chain_from_entry_names(names: list[str]) -> list[str]:
    member = _pick_archive_member(names)
    chain = _suffix_chain_from_filename(Path(member).name)
    if chain:
        return chain
    return [_leaf_type_from_member_name(member)]


_KNOWN_EXTENSION_SUFFIXES = frozenset(
    suffix for suffix, _ in _CONTAINER_SUFFIXES + _COMPRESSION_SUFFIXES + _LEAF_SUFFIXES
) | _AMBIGUOUS_LEAF_SUFFIXES


def _suffix_chain_from_filename(name: str) -> list[str]:
    lower = Path(name).name.lower()

    # Strip a trailing vendor extension before peeling archive/compression layers.
    vendor = Path(lower).suffix.lower()
    if vendor and vendor not in _KNOWN_EXTENSION_SUFFIXES:
        lower = lower[: -len(vendor)]

    chain: list[str] = []
    changed = True
    while changed:
        changed = False
        for suffix, kind in _CONTAINER_SUFFIXES + _COMPRESSION_SUFFIXES:
            if lower.endswith(suffix):
                chain.insert(0, kind)
                lower = lower[: -len(suffix)]
                changed = True
                break

    for suffix, kind in _LEAF_SUFFIXES:
        if lower.endswith(suffix):
            chain.append(kind)
            return chain

    if lower and is_ambiguous_tabular_suffix(Path(lower).suffix):
        chain.append("txt")
    elif lower:
        bare = Path(lower).suffix.lstrip(".")
        if bare:
            chain.append(bare)
    return chain


def _leaf_type_from_member_name(name: str) -> str:
    lower = name.lower()
    if is_ambiguous_tabular_suffix(Path(name).suffix):
        return "unknown"
    for suffix, kind in _LEAF_SUFFIXES:
        if lower.endswith(suffix):
            return kind
    ext = Path(name).suffix.lower().lstrip(".")
    return ext or "unknown"


def _leaf_type_from_name(name: str) -> str:
    suffix_chain = _suffix_chain_from_filename(name)
    if suffix_chain:
        return suffix_chain[-1]
    return _leaf_type_from_member_name(name)


def _normalize_kind_label(kind: str) -> str:
    token = kind.lower().strip()
    if token.startswith("x-"):
        token = token[2:]
    aliases = {
        "sqlite3": "sqlite",
        "tga": "unknown",
        "dbt": "bmp",
        "empty": "empty",
    }
    return aliases.get(token, token)


def _leaf_type_from_report(report: FileDetectionReport, display_name: str) -> str:
    structured = report.structured_format
    if structured and structured.confidence >= 60:
        detected = structured.detected_type
        if detected not in {"", "unknown", "binary"}:
            return _prefer_ambiguous_suffix_display(detected, display_name)

    if report.suggested_file_format:
        return _prefer_ambiguous_suffix_display(report.suggested_file_format, display_name)

    validation = report.validation_strategy
    if validation and validation.detected_type == "txt":
        return "txt"

    magic = report.magic_bytes
    if magic and magic.confidence >= 70:
        detected = _normalize_kind_label(magic.detected_type)
        if detected not in {"", "unknown", "zip", "tar", "gzip", "bzip2", "xz", "zstd", "lz4", "text"}:
            return detected

    if is_ambiguous_tabular_suffix(Path(display_name).suffix):
        return "txt"

    named = _leaf_type_from_member_name(display_name)
    if named != "unknown":
        return named

    extension = report.extension
    if extension and extension.metadata.get("extension"):
        ext = str(extension.metadata["extension"]).lstrip(".").lower()
        if ext:
            return ext

    return "unknown"


def _stage_type(stage: object | None) -> str:
    if stage is None:
        return ""
    return str(getattr(stage, "detected_type", "") or "")
