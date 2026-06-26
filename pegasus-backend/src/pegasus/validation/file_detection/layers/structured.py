# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:29:35Z
# --- END GENERATED FILE METADATA ---

"""Layer 7: structured format heuristics on a bounded sample."""

from __future__ import annotations

import csv
import json
import re
from io import StringIO

from pegasus.validation.file_detection.sample import FileSample
from pegasus.validation.file_detection.types import DetectionStage

_YAML_KEY_RE = re.compile(r"^[a-zA-Z_][\w.-]*\s*:", re.MULTILINE)
_XML_RE = re.compile(rb"<\?xml|<[a-zA-Z][\w:-]*[\s>]")
_JSONL_MIN_LINES = 2


def detect_structured(
    sample: FileSample,
    text_binary: DetectionStage | None,
    magic: DetectionStage | None,
) -> DetectionStage:
    if text_binary and text_binary.detected_type == "binary":
        if magic and magic.detected_type in {"parquet", "orc", "avro", "png", "pdf"}:
            return DetectionStage(
                detected_type=magic.detected_type,
                confidence=magic.confidence,
                evidence=["binary structured format from magic"],
                metadata=magic.metadata,
            )
        return DetectionStage(
            detected_type="binary",
            confidence=75,
            evidence=["classified as binary"],
            metadata={},
        )

    text = _decode_text_sample(sample)
    if not text.strip():
        return DetectionStage("unknown", 20, evidence=["empty text sample"])

    stripped = text.lstrip()
    if magic and magic.detected_type in {"json", "xml"}:
        return DetectionStage(
            detected_type=magic.detected_type,
            confidence=magic.confidence,
            evidence=["magic_bytes structured hint"],
            metadata={},
        )

    json_stage = _detect_json(stripped)
    if json_stage.confidence >= 75:
        return json_stage

    xml_stage = _detect_xml(sample.raw)
    if xml_stage.confidence >= 75:
        return xml_stage

    yaml_stage = _detect_yaml(text)
    if yaml_stage.confidence >= 70:
        return yaml_stage

    fw_stage = _detect_fixed_width(text)
    if fw_stage.confidence >= 65:
        return fw_stage

    delim_stage = _detect_delimited(text)
    if delim_stage.confidence >= 60:
        return delim_stage

    return DetectionStage(
        detected_type="unknown",
        confidence=25,
        evidence=["no structured format heuristic matched"],
        metadata={},
    )


def _decode_text_sample(sample: FileSample) -> str:
    return sample.raw.decode("utf-8-sig", errors="replace")


def _detect_json(text: str) -> DetectionStage:
    s = text.strip()
    if not s:
        return DetectionStage("unknown", 0, evidence=[])
    if s[0] in "{[":
        try:
            json.loads(s[: min(len(s), 32_000)])
            return DetectionStage("json", 90, evidence=["valid JSON document in sample"])
        except json.JSONDecodeError:
            pass
    lines = [ln for ln in text.splitlines() if ln.strip()][:20]
    if len(lines) >= _JSONL_MIN_LINES:
        ok = 0
        for ln in lines:
            try:
                json.loads(ln)
                ok += 1
            except json.JSONDecodeError:
                break
        if ok >= _JSONL_MIN_LINES:
            return DetectionStage(
                "json",
                85,
                evidence=[f"jsonl lines parsed={ok}"],
                metadata={"variant": "jsonl"},
            )
    return DetectionStage("unknown", 10, evidence=[])


def _detect_xml(raw: bytes) -> DetectionStage:
    if _XML_RE.search(raw[:4096]):
        return DetectionStage("xml", 82, evidence=["XML tag or declaration in prefix"])
    return DetectionStage("unknown", 0, evidence=[])


def _detect_yaml(text: str) -> DetectionStage:
    if text.lstrip().startswith("---"):
        return DetectionStage("yaml", 75, evidence=["YAML document start ---"])
    matches = _YAML_KEY_RE.findall(text[:4096])
    if len(matches) >= 3:
        return DetectionStage(
            "yaml",
            68,
            evidence=[f"yaml key lines={len(matches)}"],
            metadata={},
        )
    return DetectionStage("unknown", 0, evidence=[])


def _detect_delimited(text: str) -> DetectionStage:
    lines = [ln for ln in text.splitlines() if ln.strip()][:30]
    if len(lines) < 2:
        return DetectionStage("unknown", 0, evidence=[])

    for delim, name, conf in ((",", "csv", 85), ("\t", "tsv", 88), ("|", "psv", 80)):
        counts = [ln.count(delim) for ln in lines[:15]]
        if min(counts) > 0 and len(set(counts)) <= 2:
            try:
                reader = csv.reader(StringIO("\n".join(lines[:10])), delimiter=delim)
                rows = list(reader)
                if rows and all(len(r) == len(rows[0]) for r in rows[1:6] if r):
                    return DetectionStage(
                        name,
                        conf,
                        evidence=[f"consistent {name!r} delimiter counts"],
                        metadata={"delimiter": delim},
                    )
            except csv.Error:
                continue
    return DetectionStage("unknown", 0, evidence=[])


def _detect_fixed_width(text: str) -> DetectionStage:
    lines = [ln for ln in text.splitlines() if ln.strip()][:20]
    if len(lines) < 2:
        return DetectionStage("unknown", 0, evidence=[])

    for candidate in (lines[1:], lines):
        lengths = [len(ln) for ln in candidate]
        if len(set(lengths)) != 1:
            continue
        line_length = lengths[0]
        if line_length <= 20:
            continue
        if any("," in ln for ln in candidate[:5]):
            continue
        if not all("  " in ln for ln in candidate[:5]):
            continue
        return DetectionStage(
            "fixed-width",
            70,
            evidence=[f"uniform line length={line_length}"],
            metadata={"line_length": line_length},
        )
    return DetectionStage("unknown", 0, evidence=[])
