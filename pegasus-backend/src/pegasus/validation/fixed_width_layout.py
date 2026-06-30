# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:41:59Z
# --- END GENERATED FILE METADATA ---

"""Infer fixed-width column slices and date formats for the mapping UI."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pegasus.schemas.validation import FixedWidthColumnPreview, FixedWidthConfig, FixedWidthField
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.comparators.core import _DF, _lit

_STRPTIME_TO_FRIENDLY: dict[str, str] = {
    "%Y-%m-%d": "YYYY-MM-DD",
    "%m/%d/%Y": "MM/DD/YYYY",
    "%d/%m/%Y": "DD/MM/YYYY",
    "%d-%m-%Y": "DD-MM-YYYY",
    "%m-%d-%Y": "MM-DD-YYYY",
    "%d-%b-%Y": "DD-MMM-YYYY",
    "%d-%B-%Y": "DD-MMMM-YYYY",
    "%d %b %Y": "DD MMM YYYY",
    "%d %B %Y": "DD MMMM YYYY",
    "%b %d %Y": "MMM DD YYYY",
    "%B %d %Y": "MMMM DD YYYY",
    "%d.%m.%Y": "DD.MM.YYYY",
    "%Y/%m/%d": "YYYY/MM/DD",
}

_FRIENDLY_TO_STRPTIME = {v: k for k, v in _STRPTIME_TO_FRIENDLY.items()}
_COMPLEX_TYPES = (list, dict, tuple)
_SAMPLE_LINES = 20
_MIN_GUTTER = 2


def read_sample_lines_from_path(path: Path, *, max_lines: int = _SAMPLE_LINES) -> list[str]:
    if not path.is_file():
        return []
    lines: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            if raw.strip():
                lines.append(raw.rstrip("\r\n"))
            if len(lines) >= max_lines:
                break
    return lines


def sample_lines_from_adapter(
    adapter: FileDelimitedAdapter | GcsDelimitedAdapter,
    *,
    max_lines: int = _SAMPLE_LINES,
) -> list[str]:
    if isinstance(adapter, FileDelimitedAdapter):
        return read_sample_lines_from_path(adapter.path, max_lines=max_lines)
    if isinstance(adapter, GcsDelimitedAdapter):
        adapter.warm_metadata()
        prefix = adapter._ensure_prefix_bytes(512 * 1024)
        return read_sample_lines_from_bytes(prefix, max_lines=max_lines)
    return []


def read_sample_lines_from_bytes(blob: bytes, *, max_lines: int = _SAMPLE_LINES) -> list[str]:
    text = blob.decode("utf-8", errors="replace")
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.strip():
            lines.append(raw.rstrip("\r\n"))
        if len(lines) >= max_lines:
            break
    return lines


def infer_date_format_friendly(values: list[str]) -> str | None:
    """Pick the most common friendly date pattern that parses sample values."""
    scores: dict[str, int] = {}
    cleaned = [v.strip() for v in values if v and v.strip()]
    if not cleaned:
        return None
    for fmt in _DF:
        friendly = _STRPTIME_TO_FRIENDLY.get(fmt, fmt)
        hits = sum(1 for value in cleaned if _parses(value, fmt))
        if hits:
            scores[friendly] = scores.get(friendly, 0) + hits
    if not scores:
        return None
    return max(scores, key=scores.get)


def _parses(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value.strip(), fmt)
        return True
    except ValueError:
        return False


def _looks_structured(value: str) -> bool:
    return isinstance(_lit(value.strip()), _COMPLEX_TYPES)


def infer_field_type(samples: list[str]) -> str:
    cleaned = [v.strip() for v in samples if v and v.strip()]
    if not cleaned:
        return "text"
    if infer_date_format_friendly(cleaned):
        return "date"
    if any(_looks_structured(v) for v in cleaned):
        return "structured"
    if all(re.fullmatch(r"-?\d+", v) for v in cleaned):
        return "integer"
    if all(re.fullmatch(r"-?\d+(?:\.\d+)?", v) for v in cleaned):
        return "float"
    return "text"


def infer_field_boundaries(lines: list[str], *, min_gutter: int = _MIN_GUTTER) -> list[tuple[int, int]]:
    """Return (start, end) slices using all-space gutter runs shared by every line."""
    nonempty = [ln.rstrip("\r\n") for ln in lines if ln.strip()]
    if not nonempty:
        return []
    width = max(len(ln) for ln in nonempty)
    padded = [ln.ljust(width) for ln in nonempty]
    all_space = [all(ln[col] == " " for ln in padded) for col in range(width)]

    segments: list[tuple[int, int]] = []
    start = 0
    index = 0
    while index < width:
        if all_space[index]:
            gutter_end = index
            while gutter_end < width and all_space[gutter_end]:
                gutter_end += 1
            if gutter_end - index >= min_gutter and index > start:
                segments.append((start, index))
                start = gutter_end
            index = gutter_end
        else:
            index += 1
    if start < width:
        segments.append((start, width))
    return [(a, b) for a, b in segments if b > a]


def _content_runs(line: str) -> list[tuple[int, int]]:
    """Non-space spans in a line (used when gutter inference finds no columns)."""
    runs: list[tuple[int, int]] = []
    index = 0
    width = len(line)
    while index < width:
        while index < width and line[index] == " ":
            index += 1
        if index >= width:
            break
        start = index
        while index < width and line[index] != " ":
            index += 1
        runs.append((start, index))
    return runs


def _segments_for_lines(lines: list[str], *, min_gutter: int = _MIN_GUTTER) -> list[tuple[int, int]]:
    """Infer column slices for one file using space gutters, with content-run fallback."""
    segments = infer_field_boundaries(lines, min_gutter=min_gutter)
    if segments:
        return segments
    if not lines:
        return []
    run_counts = [_content_runs(ln.rstrip("\r\n")) for ln in lines if ln.strip()]
    if not run_counts:
        return []
    column_count = max(len(runs) for runs in run_counts)
    merged: list[tuple[int, int]] = []
    for col_idx in range(column_count):
        starts = [runs[col_idx][0] for runs in run_counts if len(runs) > col_idx]
        ends = [runs[col_idx][1] for runs in run_counts if len(runs) > col_idx]
        if starts and ends:
            merged.append((min(starts), max(ends)))
    return merged


def _infer_field_name(index: int, field_type: str, samples: list[str]) -> str:
    if index == 0:
        return "record_id"
    blob = " ".join(samples).lower()
    if "@" in blob:
        return "email"
    if field_type == "date":
        return "date"
    if field_type == "structured":
        return "tags" if index == 1 else "metadata" if index == 2 else f"field_{index + 1}"
    if index == 1:
        return "name"
    return f"field_{index + 1}"


def _slice_samples(lines: list[str], start: int, end: int) -> list[str]:
    return [ln[start:end].strip() if end > start else "" for ln in lines if ln.strip()]


def build_column_previews(
    source_lines: list[str],
    target_lines: list[str],
) -> list[FixedWidthColumnPreview]:
    width = max(
        max((len(ln) for ln in source_lines), default=0),
        max((len(ln) for ln in target_lines), default=0),
    )
    if width <= 0:
        return []

    src_segments = _segments_for_lines(source_lines)
    tgt_segments = _segments_for_lines(target_lines)
    column_count = max(len(src_segments), len(tgt_segments))

    columns: list[FixedWidthColumnPreview] = []
    for index in range(column_count):
        src_start, src_end = src_segments[index] if index < len(src_segments) else (0, 0)
        tgt_start, tgt_end = tgt_segments[index] if index < len(tgt_segments) else (0, 0)
        src_samples = _slice_samples(source_lines, src_start, src_end)
        tgt_samples = _slice_samples(target_lines, tgt_start, tgt_end)
        samples = [v for v in (*src_samples, *tgt_samples) if v]
        field_type = infer_field_type(samples)
        source_date_format = (
            infer_date_format_friendly(src_samples) if field_type == "date" else None
        )
        target_date_format = (
            infer_date_format_friendly(tgt_samples) if field_type == "date" else None
        )
        shared_date = source_date_format or target_date_format
        columns.append(
            FixedWidthColumnPreview(
                field_name=_infer_field_name(index, field_type, samples),
                source_start=src_start,
                source_end=src_end,
                target_start=tgt_start,
                target_end=tgt_end,
                field_type=field_type,
                width=max(src_end - src_start, tgt_end - tgt_start),
                source_sample=src_samples[0] if src_samples else "",
                target_sample=tgt_samples[0] if tgt_samples else "",
                date_format=shared_date,
                source_date_format=source_date_format,
                target_date_format=target_date_format,
                compare_enabled=True,
                is_sensitive=False,
            )
        )
    return columns


def build_layout_preview(
    source_lines: list[str],
    target_lines: list[str],
) -> dict[str, Any]:
    columns = build_column_previews(source_lines, target_lines)
    suggested_join = columns[0].field_name if columns else "record_id"
    return {
        "columns": columns,
        "suggested_join_column": suggested_join,
        "source_sample": source_lines[0] if source_lines else "",
        "target_sample": target_lines[0] if target_lines else "",
        "line_width": max(
            max((len(ln) for ln in source_lines), default=0),
            max((len(ln) for ln in target_lines), default=0),
        ),
    }


def columns_to_fixed_width_config(
    columns: list[FixedWidthColumnPreview],
    *,
    uid_column: str | None = None,
) -> FixedWidthConfig:
    uid = uid_column or (columns[0].field_name if columns else "record_id")
    fields = [
        FixedWidthField(
            field_name=col.field_name,
            source_start=col.source_start,
            source_end=col.source_end,
            target_start=col.target_start,
            target_end=col.target_end,
            field_type=col.field_type,
            structured_order_sensitive=col.structured_order_sensitive,
            date_format=col.date_format,
            source_date_format=col.source_date_format or col.date_format,
            target_date_format=col.target_date_format or col.date_format,
            compare_enabled=col.compare_enabled,
            is_sensitive=col.is_sensitive,
            source_regex_pattern=col.source_regex_pattern,
            source_regex_replacement=col.source_regex_replacement,
            target_regex_pattern=col.target_regex_pattern,
            target_regex_replacement=col.target_regex_replacement,
        )
        for col in columns
    ]
    return FixedWidthConfig(uid_column=uid, fields=fields)
