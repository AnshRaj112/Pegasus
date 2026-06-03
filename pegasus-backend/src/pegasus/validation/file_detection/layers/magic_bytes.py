"""Layer 2: magic-byte and MIME detection (bounded prefix read)."""

from __future__ import annotations

import logging

from pegasus.validation.file_detection.models import DetectionStageResult
from pegasus.validation.file_detection.sampling import FileSample

logger = logging.getLogger(__name__)

# Well-known signatures (first bytes).
_SIGNATURES: list[tuple[bytes, str, str, int]] = [
    (b"\x1f\x8b", "application/gzip", "gzip", 95),
    (b"BZh", "application/x-bzip2", "bzip2", 95),
    (b"\xfd7zXZ\x00", "application/x-xz", "xz", 95),
    (b"\x04\x22\x4d\x18", "application/x-lz4-frame", "lz4", 90),
    (b"\x28\xb5\x2f\xfd", "application/zstd", "zstd", 90),
    (b"PK\x03\x04", "application/zip", "zip", 92),
    (b"PK\x05\x06", "application/zip", "zip_empty", 85),
    (b"PK\x07\x08", "application/zip", "zip_spanned", 80),
    (b"\x1f\x9d", "application/x-compress", "compress", 85),
    (b"Rar!\x1a\x07", "application/vnd.rar", "rar", 92),
    (b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed", "7z", 92),
    (b"ustar", "application/x-tar", "tar_ustar", 70),
    (b"\x7fELF", "application/x-elf", "elf", 90),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png", 98),
    (b"%PDF", "application/pdf", "pdf", 95),
    (b"PAR1", "application/vnd.apache.parquet", "parquet", 98),
    (b"ORC", "application/orc", "orc", 85),
    (b"Obj\x01", "application/avro", "avro", 85),
    (b"\xd0\xcf\x11\xe0", "application/vnd.ms-excel", "ole_compound", 80),
    (b"\xef\xbb\xbf", "text/plain", "utf8_bom", 60),
    (b"\xff\xfe", "text/plain", "utf16_le_bom", 85),
    (b"\xfe\xff", "text/plain", "utf16_be_bom", 85),
    (b"\x00\x00\xfe\xff", "text/plain", "utf32_be_bom", 85),
    (b"\xff\xfe\x00\x00", "text/plain", "utf32_le_bom", 85),
]

# JSON/XML quick checks on prefix text
def _match_signatures(prefix: bytes) -> DetectionStageResult | None:
    for sig, mime, name, conf in _SIGNATURES:
        if prefix.startswith(sig):
            return DetectionStageResult(
                detected_type=name,
                confidence=conf,
                evidence=[f"magic bytes match {sig!r}"],
                metadata={"mime": mime},
            )
    if prefix.startswith(b"PK") and len(prefix) >= 4:
        return DetectionStageResult(
            detected_type="zip",
            confidence=75,
            evidence=["PK header (zip-family)"],
            metadata={"mime": "application/zip"},
        )
    if len(prefix) >= 262 and prefix[257:262] == b"ustar":
        return DetectionStageResult(
            detected_type="tar",
            confidence=88,
            evidence=["ustar at offset 257"],
            metadata={"mime": "application/x-tar"},
        )
    return None


def _libmagic_detect(prefix: bytes) -> DetectionStageResult | None:
    try:
        import magic  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        mime = magic.from_buffer(prefix, mime=True)
        desc = magic.from_buffer(prefix)
    except Exception as exc:  # noqa: BLE001 — libmagic can fail on odd buffers
        logger.debug("python-magic failed: %s", exc)
        return None
    if not mime or mime == "application/octet-stream":
        return None
    conf = 70 if mime != "text/plain" else 40
    return DetectionStageResult(
        detected_type=desc or mime,
        confidence=conf,
        evidence=[f"python-magic: {desc}", f"mime={mime}"],
        metadata={"mime": mime, "description": desc},
    )


def _filetype_detect(prefix: bytes) -> DetectionStageResult | None:
    try:
        import filetype  # type: ignore[import-untyped]
    except ImportError:
        return None
    kind = filetype.guess(prefix)
    if kind is None:
        return None
    return DetectionStageResult(
        detected_type=kind.extension or kind.mime,
        confidence=65,
        evidence=[f"filetype.guess → {kind.mime}"],
        metadata={"mime": kind.mime, "extension": kind.extension},
    )


def _puremagic_detect(prefix: bytes) -> DetectionStageResult | None:
    try:
        import puremagic  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        matches = puremagic.magic_string(prefix)
    except Exception:
        return None
    if not matches:
        return None
    best = matches[0]
    mime = getattr(best, "mime_type", None) or ""
    name = getattr(best, "name", None) or str(best)
    return DetectionStageResult(
        detected_type=name,
        confidence=60,
        evidence=[f"puremagic: {name}"],
        metadata={"mime": mime} if mime else {},
    )


def detect_magic_bytes(sample: FileSample) -> DetectionStageResult:
    prefix = sample.prefix_8k if len(sample.prefix) >= 8 else sample.prefix
    if not prefix:
        return DetectionStageResult(
            detected_type="empty",
            confidence=100,
            evidence=["zero-byte file"],
        )

    sig = _match_signatures(prefix)
    if sig is not None and sig.confidence >= 85:
        return sig

    for detector in (_libmagic_detect, _filetype_detect, _puremagic_detect):
        result = detector(prefix)
        if result is not None and result.confidence >= 60:
            if sig is not None:
                result.evidence.extend(sig.evidence)
                if sig.metadata.get("mime"):
                    result.metadata.setdefault("mime", sig.metadata["mime"])
            return result

    if sig is not None:
        return sig

    stripped = prefix.lstrip()
    if stripped.startswith((b"{", b"[")):
        return DetectionStageResult(
            detected_type="json_like",
            confidence=55,
            evidence=["leading { or [ after whitespace"],
            metadata={"mime": "application/json"},
        )
    if stripped.startswith(b"<"):
        return DetectionStageResult(
            detected_type="xml_like",
            confidence=50,
            evidence=["leading < after whitespace"],
            metadata={"mime": "application/xml"},
        )

    return DetectionStageResult(
        detected_type="unknown",
        confidence=10,
        evidence=["no strong magic-byte match"],
    )
