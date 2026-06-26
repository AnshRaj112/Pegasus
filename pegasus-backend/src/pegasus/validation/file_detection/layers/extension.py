# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:29:35Z
# --- END GENERATED FILE METADATA ---

"""Layer 1: extension hints (low confidence, never trusted alone)."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.file_detection.sample import FileSample
from pegasus.validation.file_detection.types import DetectionStage
from pegasus.validation.file_format import format_hint_from_suffix, is_ambiguous_tabular_suffix

_EXTENSION_CONFIDENCE = 35


def detect_extension(sample: FileSample) -> DetectionStage:
    ext = sample.path.suffix.lower()
    if is_ambiguous_tabular_suffix(ext):
        return DetectionStage(
            detected_type="txt",
            confidence=20,
            evidence=[f"suffix={ext!r} requires content sniff"],
            metadata={"extension": ext, "ambiguous_tabular": True},
        )
    mapped = format_hint_from_suffix(ext)
    if mapped:
        return DetectionStage(
            detected_type=mapped,
            confidence=_EXTENSION_CONFIDENCE,
            evidence=[f"suffix={ext!r} maps to {mapped!r}"],
            metadata={"extension": ext},
        )
    if ext:
        return DetectionStage(
            detected_type="unknown",
            confidence=10,
            evidence=[f"unmapped suffix={ext!r}"],
            metadata={"extension": ext},
        )
    return DetectionStage(
        detected_type="unknown",
        confidence=5,
        evidence=["no file extension"],
        metadata={"extension": ""},
    )


def extension_hint_for_path(path: Path) -> str | None:
    return format_hint_from_suffix(path.suffix.lower())
