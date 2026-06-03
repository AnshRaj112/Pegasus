"""Layer 3: container/archive detection (metadata only, no full extract)."""

from __future__ import annotations

import tarfile
import zipfile
from dataclasses import dataclass

from pegasus.validation.file_detection.models import DetectionStageResult
from pegasus.validation.file_detection.sampling import FileSample

DEFAULT_MAX_ARCHIVE_DEPTH = 5
DEFAULT_MAX_ARCHIVE_ENTRIES = 1000
DEFAULT_MAX_LISTED_BYTES = 64 * 1024 * 1024  # uncompressed size sum cap (estimate)


@dataclass(slots=True)
class ArchiveEntryInfo:
    name: str
    compressed_size: int
    is_dir: bool


def detect_container(
    sample: FileSample,
    *,
    magic_result: DetectionStageResult | None = None,
    max_depth: int = DEFAULT_MAX_ARCHIVE_DEPTH,
    max_entries: int = DEFAULT_MAX_ARCHIVE_ENTRIES,
) -> DetectionStageResult:
    prefix = sample.prefix_8k
    container_type = _container_type_from_magic(prefix, magic_result)
    if container_type is None:
        return DetectionStageResult(
            detected_type="none",
            confidence=75,
            evidence=["not a known archive container"],
        )

    if container_type == "zip" and _is_zip_readable(sample.path):
        entries, nested = _inspect_zip(sample.path, max_entries=max_entries, max_depth=max_depth)
        return _container_result(container_type, entries, nested, confidence=90)

    if container_type == "tar" and tarfile.is_tarfile(sample.path):
        entries, nested = _inspect_tar(sample.path, max_entries=max_entries)
        return _container_result(container_type, entries, nested, confidence=88)

    return DetectionStageResult(
        detected_type=container_type,
        confidence=70,
        evidence=[f"container signature {container_type} (metadata scan skipped or unavailable)"],
        metadata={"entry_count": 0},
    )


def _container_type_from_magic(
    prefix: bytes,
    magic_result: DetectionStageResult | None,
) -> str | None:
    if prefix.startswith(b"PK\x03\x04") or prefix.startswith(b"PK\x05\x06"):
        return "zip"
    if magic_result and magic_result.detected_type in {"zip", "7z", "rar", "tar", "tar_ustar"}:
        t = magic_result.detected_type
        return "tar" if t == "tar_ustar" else t
    if len(prefix) >= 262 and prefix[257:262] == b"ustar":
        return "tar"
    if prefix.startswith(b"Rar!\x1a\x07"):
        return "rar"
    if prefix.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    return None


def _is_zip_readable(path) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def _inspect_zip(
    path,
    *,
    max_entries: int,
    max_depth: int,
) -> tuple[list[ArchiveEntryInfo], bool]:
    entries: list[ArchiveEntryInfo] = []
    nested = False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            for info in zf.infolist():
                if len(entries) >= max_entries:
                    break
                name = info.filename
                entries.append(
                    ArchiveEntryInfo(
                        name=name,
                        compressed_size=info.compress_size,
                        is_dir=name.endswith("/"),
                    )
                )
                lower = name.lower()
                if any(lower.endswith(ext) for ext in (".zip", ".tar", ".gz", ".7z", ".rar")):
                    nested = True
    except (zipfile.BadZipFile, OSError):
        return [], False
    _ = max_depth  # reserved for recursive nested walk (depth-limited)
    return entries, nested


def _inspect_tar(path, *, max_entries: int) -> tuple[list[ArchiveEntryInfo], bool]:
    entries: list[ArchiveEntryInfo] = []
    nested = False
    try:
        with tarfile.open(path, "r:*") as tf:
            for member in tf.getmembers():
                if len(entries) >= max_entries:
                    break
                entries.append(
                    ArchiveEntryInfo(
                        name=member.name,
                        compressed_size=member.size,
                        is_dir=member.isdir(),
                    )
                )
                lower = member.name.lower()
                if any(lower.endswith(ext) for ext in (".zip", ".tar", ".gz", ".7z", ".rar")):
                    nested = True
    except (tarfile.TarError, OSError):
        return [], False
    return entries, nested


def _container_result(
    container_type: str,
    entries: list[ArchiveEntryInfo],
    nested: bool,
    *,
    confidence: int,
) -> DetectionStageResult:
    names = [e.name for e in entries[:20]]
    evidence = [f"archive type {container_type}", f"listed {len(entries)} entries (cap applied)"]
    if nested:
        evidence.append("nested archive members detected")
    return DetectionStageResult(
        detected_type=container_type,
        confidence=confidence,
        evidence=evidence,
        metadata={
            "entry_count": len(entries),
            "sample_entries": names,
            "nested_archives": nested,
        },
    )
