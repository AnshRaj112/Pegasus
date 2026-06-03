"""Layer 4: compression detection and underlying payload hints."""

from __future__ import annotations

from pegasus.validation.file_detection.models import DetectionStageResult
from pegasus.validation.file_detection.sampling import FileSample

_COMPRESSION_MAGICS: list[tuple[bytes, str, int]] = [
    (b"\x1f\x8b", "gzip", 95),
    (b"BZh", "bzip2", 90),
    (b"\xfd7zXZ\x00", "xz", 95),
    (b"\x04\x22\x4d\x18", "lz4", 88),
    (b"\x28\xb5\x2f\xfd", "zstd", 90),
    (b"\x1f\x9d", "compress", 85),
]


def detect_compression(
    sample: FileSample,
    *,
    magic_result: DetectionStageResult | None = None,
) -> DetectionStageResult:
    prefix = sample.prefix_4k
    for sig, name, conf in _COMPRESSION_MAGICS:
        if prefix.startswith(sig):
            payload_hint = _guess_compressed_payload(prefix, name)
            evidence = [f"compression signature {name}"]
            meta: dict[str, object] = {"algorithm": name}
            if payload_hint:
                evidence.append(f"likely inner format: {payload_hint}")
                meta["inner_format_hint"] = payload_hint
            return DetectionStageResult(
                detected_type=name,
                confidence=conf,
                evidence=evidence,
                metadata=meta,
            )

    if magic_result and magic_result.detected_type in {"gzip", "bzip2", "xz", "lz4", "zstd"}:
        return DetectionStageResult(
            detected_type=magic_result.detected_type,
            confidence=magic_result.confidence - 5,
            evidence=[f"inherited from magic layer: {magic_result.detected_type}"],
        )

    return DetectionStageResult(
        detected_type="none",
        confidence=80,
        evidence=["no compression signature in prefix"],
    )


def _guess_compressed_payload(prefix: bytes, algorithm: str) -> str | None:
    """Best-effort inner type without decompressing the full file."""
    if algorithm != "gzip" or len(prefix) < 12:
        return None
    # gzip member: skip 10-byte header + optional extras; deflate stream not parsed here.
    # Filename extension on .csv.gz etc. is handled in extension layer.
    return None


def is_compressed_type(detected_type: str) -> bool:
    return detected_type in {"gzip", "bzip2", "xz", "lz4", "zstd", "compress"}
