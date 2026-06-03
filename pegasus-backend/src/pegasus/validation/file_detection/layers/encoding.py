"""Layer 5: encoding detection (heuristics, sample-only decode)."""

from __future__ import annotations

import base64
import re
from urllib.parse import unquote_to_bytes

from pegasus.validation.file_detection.models import DetectionStageResult
from pegasus.validation.file_detection.sampling import FileSample

_HEX_RE = re.compile(rb"^[0-9a-fA-F\s]+$")
_B64_RE = re.compile(rb"^[A-Za-z0-9+/=\s]+$")


def detect_encoding(
    sample: FileSample,
    *,
    magic_result: DetectionStageResult | None = None,
) -> DetectionStageResult:
    prefix = sample.prefix_8k
    if not prefix:
        return DetectionStageResult("utf-8", 50, ["empty file defaults to utf-8"])

    if magic_result:
        dt = magic_result.detected_type
        if dt == "utf16_le_bom":
            return DetectionStageResult("utf-16-le", 90, ["UTF-16 LE BOM"], {"bom": True})
        if dt == "utf16_be_bom":
            return DetectionStageResult("utf-16-be", 90, ["UTF-16 BE BOM"], {"bom": True})
        if dt == "utf32_le_bom":
            return DetectionStageResult("utf-32-le", 88, ["UTF-32 LE BOM"], {"bom": True})
        if dt == "utf32_be_bom":
            return DetectionStageResult("utf-32-be", 88, ["UTF-32 BE BOM"], {"bom": True})
        if dt == "utf8_bom":
            return DetectionStageResult("utf-8-sig", 85, ["UTF-8 BOM"], {"bom": True})

    hex_result = _detect_hex_encoding(prefix)
    if hex_result is not None:
        return hex_result

    b64_result = _detect_base64_encoding(prefix)
    if b64_result is not None:
        return b64_result

    url_result = _detect_url_encoding(prefix)
    if url_result is not None:
        return url_result

    utf8_conf = _utf8_confidence(prefix)
    if utf8_conf >= 70:
        return DetectionStageResult(
            "utf-8",
            utf8_conf,
            [f"valid UTF-8 ratio high ({utf8_conf}%)"],
        )

    if _looks_utf16(prefix):
        return DetectionStageResult(
            "utf-16",
            55,
            ["alternating zero bytes suggest UTF-16"],
        )

    return DetectionStageResult(
        "unknown",
        30,
        ["encoding could not be determined confidently"],
    )


def _detect_hex_encoding(prefix: bytes) -> DetectionStageResult | None:
    sample = prefix[:512].strip()
    if len(sample) < 16 or len(sample) % 2 != 0:
        return None
    if not _HEX_RE.match(sample):
        return None
    try:
        bytes.fromhex(sample.decode("ascii"))
    except ValueError:
        return None
    return DetectionStageResult(
        "hex",
        75,
        ["prefix looks hexadecimal-encoded"],
        {"decoded_sample_bytes": min(len(sample) // 2, 256)},
    )


def _detect_base64_encoding(prefix: bytes) -> DetectionStageResult | None:
    sample = prefix[:1024].strip()
    if len(sample) < 24 or len(sample) % 4 != 0:
        return None
    if not _B64_RE.match(sample):
        return None
    try:
        decoded = base64.b64decode(sample, validate=True)
    except Exception:
        return None
    if len(decoded) < 4:
        return None
    return DetectionStageResult(
        "base64",
        70,
        ["prefix decodes as valid base64"],
        {"decoded_prefix_len": len(decoded)},
    )


def _detect_url_encoding(prefix: bytes) -> DetectionStageResult | None:
    try:
        text = prefix[:512].decode("ascii", errors="strict")
    except UnicodeDecodeError:
        return None
    if "%" not in text or text.count("%") < 3:
        return None
    try:
        unquote_to_bytes(text)
    except Exception:
        return None
    return DetectionStageResult(
        "url_encoded",
        60,
        ["percent-escapes in ASCII prefix"],
    )


def _utf8_confidence(data: bytes) -> int:
    if not data:
        return 50
    try:
        data.decode("utf-8")
        return 95
    except UnicodeDecodeError:
        pass
    # Partial: count decodable chunks
    ok = 0
    step = 4096
    for i in range(0, len(data), step):
        chunk = data[i : i + step]
        try:
            chunk.decode("utf-8")
            ok += len(chunk)
        except UnicodeDecodeError:
            pass
    return int(100 * ok / len(data)) if data else 0


def _looks_utf16(data: bytes) -> bool:
    if len(data) < 8:
        return False
    zeros_even = sum(1 for i in range(0, min(64, len(data)), 2) if data[i] == 0)
    zeros_odd = sum(1 for i in range(1, min(64, len(data)), 2) if data[i] == 0)
    return zeros_even > 20 or zeros_odd > 20
