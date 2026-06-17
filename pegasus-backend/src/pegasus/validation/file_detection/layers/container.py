# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:51:18Z
# --- END GENERATED FILE METADATA ---

"""Layer 3: container/archive metadata (no full extract)."""

from __future__ import annotations

import tarfile
import zipfile

from pegasus.validation.file_detection.sample import FileSample
from pegasus.validation.file_detection.types import DetectionStage

MAX_ARCHIVE_ENTRIES = 1000
MAX_LIST_NAME_BYTES = 256


def detect_container(sample: FileSample, magic: DetectionStage | None) -> DetectionStage:
    prefix = sample.prefix_4k
    kind = (magic.detected_type if magic else "") or ""

    if prefix.startswith(b"PK") or kind == "zip":
        return _inspect_zip(sample)
    if kind == "tar" or _tar_header_in_prefix(prefix):
        return _inspect_tar(sample)
    if kind in {"7z", "rar"}:
        return DetectionStage(
            detected_type=kind,
            confidence=magic.confidence if magic else 85,
            evidence=[f"{kind} magic identified; deep listing deferred"],
            metadata={"listing": "deferred", "strategy_hint": "container"},
        )
    return DetectionStage(
        detected_type="none",
        confidence=85,
        evidence=["not a container format"],
        metadata={},
    )


def _tar_header_in_prefix(prefix: bytes) -> bool:
    if len(prefix) < 262:
        return False
    return prefix[257:262] in (b"ustar", b"ustar\x00")


def _inspect_zip(sample: FileSample) -> DetectionStage:
    evidence: list[str] = []
    names: list[str] = []
    nested = False
    truncated = False
    try:
        with zipfile.ZipFile(sample.path, "r") as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ARCHIVE_ENTRIES:
                truncated = True
                infos = infos[:MAX_ARCHIVE_ENTRIES]
            for info in infos:
                name = info.filename[:MAX_LIST_NAME_BYTES]
                names.append(name)
                low = name.lower()
                if low.endswith((".zip", ".tar", ".gz", ".7z", ".rar")):
                    nested = True
            evidence.append(f"zip entries={len(infos)}")
    except (zipfile.BadZipFile, OSError) as exc:
        return DetectionStage(
            detected_type="zip",
            confidence=60,
            evidence=[f"zip magic but listing failed: {exc}"],
            metadata={"error": str(exc)},
        )
    return DetectionStage(
        detected_type="zip",
        confidence=92,
        evidence=evidence,
        metadata={
            "entry_count": len(names),
            "entries_truncated": truncated,
            "nested_archive_hint": nested,
            "entry_names_sample": names[:20],
            "strategy_hint": "container",
        },
    )


def _inspect_tar(sample: FileSample) -> DetectionStage:
    evidence: list[str] = []
    names: list[str] = []
    nested = False
    truncated = False
    try:
        with tarfile.open(sample.path, "r:*") as tf:
            members = tf.getmembers()
            if len(members) > MAX_ARCHIVE_ENTRIES:
                truncated = True
                members = members[:MAX_ARCHIVE_ENTRIES]
            for m in members:
                if not m.isfile():
                    continue
                name = m.name[:MAX_LIST_NAME_BYTES]
                names.append(name)
                low = name.lower()
                if low.endswith((".zip", ".tar", ".gz", ".7z", ".rar")):
                    nested = True
            evidence.append(f"tar file members={len(names)}")
    except (tarfile.TarError, OSError) as exc:
        return DetectionStage(
            detected_type="tar",
            confidence=60,
            evidence=[f"tar open failed: {exc}"],
            metadata={"error": str(exc)},
        )
    return DetectionStage(
        detected_type="tar",
        confidence=90,
        evidence=evidence,
        metadata={
            "entry_count": len(names),
            "entries_truncated": truncated,
            "nested_archive_hint": nested,
            "entry_names_sample": names[:20],
            "strategy_hint": "container",
        },
    )
