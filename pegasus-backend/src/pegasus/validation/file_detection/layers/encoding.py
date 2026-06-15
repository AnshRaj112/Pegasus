# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:08:54Z
# --- END GENERATED FILE METADATA ---

"""Layer 5: character encoding and transform detection."""

from __future__ import annotations

import base64
import binascii
import re
from urllib.parse import unquote_to_bytes

from pegasus.validation.file_detection.layers import magic_bytes as magic_layer
from pegasus.validation.file_detection.sample import FileSample
from pegasus.validation.file_detection.types import DetectionStage

_HEX_RE = re.compile(rb"^[0-9a-fA-F\s]+$")
_B64_RE = re.compile(rb"^[A-Za-z0-9+/=\s]+$")


def detect_encoding(sample: FileSample) -> DetectionStage:
    raw = sample.prefix_8k
    if raw.startswith(b"\xef\xbb\xbf"):
        return _utf_stage("utf-8-sig", 92, ["UTF-8 BOM"])
    if raw.startswith(b"\xff\xfe\x00\x00") or raw.startswith(b"\x00\x00\xfe\xff"):
        endian = "le" if raw.startswith(b"\xff\xfe") else "be"
        return _utf_stage(f"utf-32-{endian}", 85, [f"UTF-32 {endian} BOM"])
    if raw.startswith(b"\xff\xfe"):
        return _utf_stage("utf-16-le", 88, ["UTF-16 LE BOM"])
    if raw.startswith(b"\xfe\xff"):
        return _utf_stage("utf-16-be", 88, ["UTF-16 BE BOM"])

    stripped = raw.lstrip()
    if stripped and _HEX_RE.match(stripped[: min(512, len(stripped))]):
        decoded = _try_hex_decode(stripped[:4096])
        if decoded:
            inner = magic_layer.detect_magic_bytes(
                _sample_with_bytes(sample, decoded)
            )
            return DetectionStage(
                detected_type="hex",
                confidence=80,
                evidence=["hexadecimal prefix", f"decoded inner={inner.detected_type!r}"],
                metadata={"inner_type": inner.detected_type, "decode_sample_bytes": len(decoded)},
            )

    if stripped and _B64_RE.match(stripped[: min(512, len(stripped))]) and len(stripped) % 4 == 0:
        decoded = _try_b64_decode(stripped[:4096])
        if decoded:
            inner = magic_layer.detect_magic_bytes(_sample_with_bytes(sample, decoded))
            return DetectionStage(
                detected_type="base64",
                confidence=78,
                evidence=["base64-like prefix", f"decoded inner={inner.detected_type!r}"],
                metadata={"inner_type": inner.detected_type, "decode_sample_bytes": len(decoded)},
            )

    if b"%" in raw[:256] and _looks_url_encoded(raw[:512]):
        try:
            decoded = unquote_to_bytes(raw[:2048].decode("ascii", errors="ignore"))
            if decoded:
                return DetectionStage(
                    detected_type="url-encoded",
                    confidence=70,
                    evidence=["percent-encoding in prefix"],
                    metadata={"decode_sample_bytes": len(decoded)},
                )
        except ValueError:
            pass

    ratio = _utf8_valid_ratio(raw)
    if ratio >= 0.98:
        return _utf_stage("utf-8", 85, [f"utf-8 valid ratio={ratio:.2f}"])
    if ratio >= 0.85:
        return _utf_stage("utf-8", 65, [f"utf-8 mostly valid ratio={ratio:.2f}"])
    return DetectionStage(
        detected_type="binary",
        confidence=55,
        evidence=[f"low utf-8 validity ratio={ratio:.2f}"],
        metadata={"utf8_valid_ratio": ratio},
    )


def _utf_stage(name: str, confidence: int, evidence: list[str]) -> DetectionStage:
    meta = {}
    if name.startswith("utf-16") or name.startswith("utf-32"):
        meta["strategy_hint"] = "transcode_first"
    return DetectionStage(
        detected_type=name,
        confidence=confidence,
        evidence=evidence,
        metadata=meta,
    )


def _utf8_valid_ratio(data: bytes) -> float:
    if not data:
        return 1.0
    try:
        data.decode("utf-8")
        return 1.0
    except UnicodeDecodeError:
        pass
    valid = 0
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b < 0x80:
            valid += 1
            i += 1
        elif b < 0xE0 and i + 1 < n:
            valid += 1
            i += 2
        elif b < 0xF0 and i + 2 < n:
            valid += 1
            i += 3
        elif b < 0xF8 and i + 3 < n:
            valid += 1
            i += 4
        else:
            i += 1
    return valid / max(n, 1)


def _try_hex_decode(data: bytes) -> bytes | None:
    try:
        cleaned = re.sub(rb"\s+", b"", data)
        if len(cleaned) < 4 or len(cleaned) % 2:
            return None
        return binascii.unhexlify(cleaned[:4096])
    except (binascii.Error, ValueError):
        return None


def _try_b64_decode(data: bytes) -> bytes | None:
    try:
        cleaned = re.sub(rb"\s+", b"", data)
        return base64.b64decode(cleaned, validate=True)[:4096]
    except (binascii.Error, ValueError):
        return None


def _looks_url_encoded(data: bytes) -> bool:
    text = data.decode("ascii", errors="ignore")
    return text.count("%") >= 2 and "%20" in text or "%3D" in text


def _sample_with_bytes(sample: FileSample, decoded: bytes):
    from pegasus.validation.file_detection.sample import FileSample as FS

    return FS(
        path=sample.path,
        file_size_bytes=sample.file_size_bytes,
        raw=decoded[: sample.bytes_read],
        bytes_read=min(len(decoded), sample.bytes_read),
    )
