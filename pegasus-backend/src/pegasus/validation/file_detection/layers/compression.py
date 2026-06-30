# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T10:54:38Z
# --- END GENERATED FILE METADATA ---

"""Layer 4: compression format detection."""

from __future__ import annotations

from pegasus.validation.file_detection.sample import FileSample
from pegasus.validation.file_detection.types import DetectionStage

_COMPRESSION_MAGIC: list[tuple[bytes, str, int]] = [
    (b"\x1f\x8b", "gzip", 95),
    (b"BZh", "bzip2", 93),
    (b"\xfd7zXZ\x00", "xz", 93),
    (b"\x28\xb5\x2f\xfd", "zstd", 92),
    (b"\x04\x22\x4d\x18", "lz4", 88),
]


def detect_compression(sample: FileSample, magic: DetectionStage | None) -> DetectionStage:
    prefix = sample.prefix_4k
    for sig, kind, conf in _COMPRESSION_MAGIC:
        if prefix.startswith(sig):
            return DetectionStage(
                detected_type=kind,
                confidence=conf,
                evidence=[f"compression signature {sig[:6]!r}"],
                metadata={"strategy_hint": "decompress_first"},
            )
    if magic and magic.detected_type in {"gzip", "bzip2", "xz", "zstd", "lz4"}:
        return DetectionStage(
            detected_type=magic.detected_type,
            confidence=max(70, magic.confidence - 5),
            evidence=["inherited from magic_bytes layer"],
            metadata={"strategy_hint": "decompress_first"},
        )
    return DetectionStage(
        detected_type="none",
        confidence=90,
        evidence=["no compression signature"],
        metadata={},
    )
