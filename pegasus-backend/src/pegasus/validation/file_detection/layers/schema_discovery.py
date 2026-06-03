"""Layer 8: schema hints from sample windows only."""

from __future__ import annotations

import csv
import io
import json

from pegasus.validation.file_detection.models import DetectionStageResult
from pegasus.validation.file_detection.sampling import FileSample


def discover_schema_hint(
    sample: FileSample,
    *,
    structured: DetectionStageResult | None = None,
) -> DetectionStageResult:
    if structured is None or structured.detected_type in {"unknown", "empty"}:
        return DetectionStageResult(
            "unavailable",
            0,
            ["structured format unknown; schema not inferred"],
        )

    fmt = structured.detected_type
    if fmt in {"csv", "tsv", "psv"}:
        return _tabular_schema(sample, structured)
    if fmt == "json":
        return _json_schema(sample)
    if fmt == "jsonl":
        return _jsonl_schema(sample)
    if fmt == "fixed_width":
        return DetectionStageResult(
            "inferred_positions",
            40,
            ["fixed-width: column positions require layout rules"],
            {"schema_available": False},
        )

    return DetectionStageResult(
        "unavailable",
        10,
        [f"schema discovery not implemented for {fmt}"],
    )


def _tabular_schema(
    sample: FileSample,
    structured: DetectionStageResult,
) -> DetectionStageResult:
    delim = structured.metadata.get("delimiter", ",")
    text = sample.prefix.decode("utf-8", errors="replace")
    lines = [ln for ln in text.splitlines()[:5] if ln.strip()]
    if not lines:
        return DetectionStageResult("unavailable", 0, ["no lines"])

    try:
        reader = csv.reader(io.StringIO("\n".join(lines[:3])), delimiter=str(delim))
        rows = list(reader)
    except csv.Error:
        return DetectionStageResult("unavailable", 20, ["csv parse failed on sample"])

    if not rows:
        return DetectionStageResult("unavailable", 0, ["no rows parsed"])

    header = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else []
    columns = [
        {
            "name": name or f"col_{i}",
            "inferred_type": _infer_cell_type(
                [r[i] if i < len(r) else "" for r in data_rows[:5]]
            ),
            "nullable": True,
        }
        for i, name in enumerate(header)
    ]
    has_header = _looks_like_header(header, data_rows)
    return DetectionStageResult(
        "tabular_columns",
        65 if has_header else 45,
        [
            f"{len(columns)} columns from sample",
            f"header_row={'yes' if has_header else 'uncertain'}",
        ],
        {
            "schema_available": True,
            "columns": columns[:50],
            "column_count": len(columns),
            "has_header": has_header,
        },
    )


def _json_schema(sample: FileSample) -> DetectionStageResult:
    text = sample.prefix.decode("utf-8", errors="replace").lstrip()
    try:
        doc = json.loads(text[: min(len(text), 512 * 1024)])
    except json.JSONDecodeError:
        return DetectionStageResult("unavailable", 15, ["JSON sample parse failed"])
    keys = list(doc.keys())[:30] if isinstance(doc, dict) else []
    return DetectionStageResult(
        "hierarchical_keys",
        70 if keys else 50,
        [f"top-level keys: {len(keys)}"],
        {"schema_available": bool(keys), "top_level_keys": keys},
    )


def _jsonl_schema(sample: FileSample) -> DetectionStageResult:
    keys: set[str] = set()
    for line in sample.prefix.decode("utf-8", errors="replace").splitlines()[:10]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            keys.update(row.keys())
    return DetectionStageResult(
        "hierarchical_keys",
        60 if keys else 30,
        [f"union of keys across sample lines: {len(keys)}"],
        {"schema_available": bool(keys), "top_level_keys": sorted(keys)[:30]},
    )


def _looks_like_header(header: list[str], data_rows: list[list[str]]) -> bool:
    if not header or not data_rows:
        return False
    numeric_header = sum(1 for h in header if h.replace(".", "", 1).isdigit())
    if numeric_header > len(header) // 2:
        return False
    return any(h and not h.isdigit() for h in header)


def _infer_cell_type(values: list[str]) -> str:
    if not values:
        return "unknown"
    cleaned = [v.strip() for v in values if v.strip()]
    if not cleaned:
        return "null"
    if all(v.isdigit() for v in cleaned):
        return "integer"
    if all(_is_float(v) for v in cleaned):
        return "float"
    return "string"


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False
