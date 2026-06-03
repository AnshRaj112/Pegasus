"""Layer 1: extension hints (low confidence, never trusted alone)."""

from __future__ import annotations

from pegasus.validation.file_detection.models import DetectionStageResult
from pegasus.validation.file_detection.sampling import FileSample

# Extension → likely structured type (hint only).
_EXTENSION_HINTS: dict[str, tuple[str, int]] = {
    ".csv": ("csv", 25),
    ".tsv": ("tsv", 30),
    ".psv": ("psv", 30),
    ".txt": ("text", 15),
    ".dat": ("text", 15),
    ".json": ("json", 35),
    ".jsonl": ("jsonl", 35),
    ".ndjson": ("jsonl", 35),
    ".xml": ("xml", 35),
    ".yaml": ("yaml", 30),
    ".yml": ("yaml", 30),
    ".parquet": ("parquet", 40),
    ".orc": ("orc", 40),
    ".avro": ("avro", 40),
    ".xlsx": ("excel", 40),
    ".xls": ("excel", 35),
    ".zip": ("zip", 30),
    ".tar": ("tar", 30),
    ".gz": ("gzip", 30),
    ".gzip": ("gzip", 30),
    ".bz2": ("bzip2", 30),
    ".xz": ("xz", 30),
    ".7z": ("7z", 35),
    ".rar": ("rar", 35),
    ".fw": ("fixed_width", 25),
    ".fixed": ("fixed_width", 25),
}


def detect_extension_hint(sample: FileSample) -> DetectionStageResult:
    ext = sample.suffix
    if not ext:
        return DetectionStageResult(
            detected_type="unknown",
            confidence=0,
            evidence=["no file extension"],
        )
    hint = _EXTENSION_HINTS.get(ext)
    if hint is None:
        return DetectionStageResult(
            detected_type="unknown",
            confidence=5,
            evidence=[f"unrecognized extension {ext!r}"],
            metadata={"extension": ext},
        )
    detected, conf = hint
    return DetectionStageResult(
        detected_type=detected,
        confidence=conf,
        evidence=[f"extension {ext!r} suggests {detected}"],
        metadata={"extension": ext},
    )
