# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-03T15:13:31+05:30
# --- END GENERATED FILE METADATA ---

"""Layer 8: schema hints from bounded sample only."""

from __future__ import annotations

import csv
import json
from io import StringIO

from pegasus.validation.file_detection.sample import FileSample
from pegasus.validation.file_detection.types import DetectionStage


def detect_schema_hint(
    sample: FileSample,
    structured: DetectionStage | None,
) -> DetectionStage:
    if not structured or structured.confidence < 50:
        return DetectionStage(
            detected_type="none",
            confidence=80,
            evidence=["no structured format to infer schema from"],
            metadata={},
        )

    fmt = structured.detected_type
    text = sample.raw.decode("utf-8", errors="replace")

    if fmt in {"csv", "tsv", "psv"}:
        return _tabular_schema(text, structured.metadata.get("delimiter", ","), fmt)
    if fmt == "json":
        return _json_schema(text, structured.metadata.get("variant"))
    if fmt == "fixed-width":
        return DetectionStage(
            detected_type="fixed-width",
            confidence=60,
            evidence=["fixed-width layout inference deferred"],
            metadata={"columns": []},
        )
    return DetectionStage(
        detected_type="none",
        confidence=70,
        evidence=[f"schema discovery not implemented for {fmt!r}"],
        metadata={},
    )


def _tabular_schema(text: str, delimiter: str, fmt: str) -> DetectionStage:
    lines = [ln for ln in text.splitlines() if ln.strip()][:15]
    if not lines:
        return DetectionStage("none", 30, evidence=["no lines in sample"])
    try:
        reader = csv.reader(StringIO(lines[0]), delimiter=delimiter)
        header = next(reader)
    except (csv.Error, StopIteration):
        return DetectionStage("none", 30, evidence=["could not parse header row"])
    columns = [
        {"name": name.strip() or f"col_{i}", "inferred_type": "string", "nullable": True}
        for i, name in enumerate(header)
    ]
    return DetectionStage(
        detected_type=fmt,
        confidence=72,
        evidence=[f"inferred {len(columns)} columns from header row"],
        metadata={"columns": columns, "has_header": True},
    )


def _json_schema(text: str, variant: str | None) -> DetectionStage:
    if variant == "jsonl":
        keys: set[str] = set()
        for ln in text.splitlines()[:20]:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                keys.update(obj.keys())
        return DetectionStage(
            detected_type="json",
            confidence=70,
            evidence=[f"jsonl key union size={len(keys)}"],
            metadata={"top_level_keys": sorted(keys)[:50]},
        )
    try:
        obj = json.loads(text[: min(len(text), 32_000)])
    except json.JSONDecodeError:
        return DetectionStage("none", 30, evidence=["json parse failed for schema"])
    if isinstance(obj, dict):
        keys = list(obj.keys())[:50]
        return DetectionStage(
            detected_type="json",
            confidence=75,
            evidence=[f"top-level object keys={len(keys)}"],
            metadata={"top_level_keys": keys},
        )
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        keys = list(obj[0].keys())[:50]
        return DetectionStage(
            detected_type="json",
            confidence=72,
            evidence=["array of objects; schema from first element"],
            metadata={"top_level_keys": keys},
        )
    return DetectionStage(
        detected_type="json",
        confidence=50,
        evidence=["json without object schema"],
        metadata={},
    )
