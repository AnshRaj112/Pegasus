"""Layer 7: lightweight structured format detection (sample only)."""

from __future__ import annotations

import json
import re

from pegasus.validation.file_detection.models import DetectionStageResult
from pegasus.validation.file_detection.sampling import FileSample

_CSV_DELIMS = (",", "\t", "|", ";")
_YAML_KEY_RE = re.compile(r"^[a-zA-Z_][\w.-]*\s*:", re.MULTILINE)


def detect_structured_format(
    sample: FileSample,
    *,
    text_binary: DetectionStageResult | None = None,
    extension_hint: DetectionStageResult | None = None,
) -> DetectionStageResult:
    if text_binary and text_binary.detected_type == "binary":
        ext = extension_hint.detected_type if extension_hint else "unknown"
        if ext in {"parquet", "orc", "avro", "excel"}:
            return DetectionStageResult(
                ext,
                extension_hint.confidence if extension_hint else 50,
                [f"binary structured format {ext}"],
            )
        return DetectionStageResult(
            "unknown",
            20,
            ["binary payload; structured text formats skipped"],
        )

    text = _decode_text_sample(sample)
    if not text.strip():
        return DetectionStageResult("empty", 90, ["no text content in sample"])

    jsonl = _detect_jsonl(text)
    if jsonl is not None:
        return jsonl

    json_doc = _detect_json(text)
    if json_doc is not None:
        return json_doc

    xml = _detect_xml(text)
    if xml is not None:
        return xml

    yaml_fmt = _detect_yaml(text)
    if yaml_fmt is not None:
        return yaml_fmt

    delim = _detect_delimited(text)
    if delim is not None:
        return delim

    fixed = _detect_fixed_width(text)
    if fixed is not None:
        return fixed

    return DetectionStageResult(
        "unknown",
        25,
        ["no structured format matched in sample window"],
    )


def _decode_text_sample(sample: FileSample) -> str:
    return sample.prefix.decode("utf-8", errors="replace")


def _detect_json(text: str) -> DetectionStageResult | None:
    stripped = text.lstrip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        json.loads(stripped[: min(len(stripped), 256 * 1024)])
    except json.JSONDecodeError:
        return DetectionStageResult(
            "json",
            45,
            ["starts with JSON token but full sample parse failed"],
        )
    return DetectionStageResult(
        "json",
        88,
        ["valid JSON document in prefix sample"],
    )


def _detect_jsonl(text: str) -> DetectionStageResult | None:
    lines = [ln for ln in text.splitlines()[:50] if ln.strip()]
    if len(lines) < 2:
        return None
    ok = 0
    for line in lines[:20]:
        try:
            json.loads(line)
            ok += 1
        except json.JSONDecodeError:
            break
    if ok >= 2 and ok >= len(lines[:20]) * 0.8:
        return DetectionStageResult(
            "jsonl",
            82,
            [f"{ok} consecutive JSON lines in sample"],
        )
    return None


def _detect_xml(text: str) -> DetectionStageResult | None:
    stripped = text.lstrip()
    if not stripped.startswith("<"):
        return None
    if re.search(r"<\?xml\s", stripped[:200], re.I) or re.search(
        r"<[A-Za-z_][\w.-]*", stripped[:500]
    ):
        return DetectionStageResult(
            "xml",
            75,
            ["XML declaration or element in sample"],
        )
    return None


def _detect_yaml(text: str) -> DetectionStageResult | None:
    if _YAML_KEY_RE.search(text[:4096]) and ":" in text[:4096]:
        if not text.lstrip().startswith(("{", "[")):
            return DetectionStageResult(
                "yaml",
                55,
                ["key: value patterns in sample (heuristic)"],
            )
    return None


def _detect_delimited(text: str) -> DetectionStageResult | None:
    lines = [ln for ln in text.splitlines()[:30] if ln.strip()]
    if len(lines) < 2:
        return None
    best_delim: str | None = None
    best_score = 0
    for delim in _CSV_DELIMS:
        counts = [line.count(delim) for line in lines[:15]]
        if min(counts) <= 0:
            continue
        if max(counts) - min(counts) > 2:
            continue
        score = min(counts)
        if score > best_score:
            best_score = score
            best_delim = delim
    if best_delim is None:
        return None
    name = {"\t": "tsv", "|": "psv", ";": "csv", ",": "csv"}[best_delim]
    return DetectionStageResult(
        name,
        min(90, 50 + best_score * 5),
        [f"consistent delimiter {best_delim!r} across sample lines"],
        {"delimiter": best_delim},
    )


def _detect_fixed_width(text: str) -> DetectionStageResult | None:
    lines = [ln for ln in text.splitlines()[:10] if ln.strip()]
    if len(lines) < 3:
        return None
    lengths = {len(ln) for ln in lines[:8]}
    if len(lengths) == 1 and next(iter(lengths)) >= 20:
        if all(" " in ln and "," not in ln for ln in lines[:5]):
            return DetectionStageResult(
                "fixed_width",
                60,
                ["uniform line lengths without delimiters"],
                {"line_length": next(iter(lengths))},
            )
    return None
