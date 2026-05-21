"""Infer fixed-width column slices from sample lines."""

from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"\S+")

# Suggested names when a line has the common Pegasus token count/order.
_NAMED_BY_INDEX: tuple[str, ...] = ("id", "name", "email", "dob", "field_5", "field_6")


def infer_columns_from_line(line: str) -> list[dict[str, Any]]:
    """Return column definitions with 0-indexed half-open slice positions per field.

    Ends are taken at the next token's start (or end of line for the last field), not at
    ``match.end()``, so padded fixed-width spans are included. Using token end alone truncates
    values (e.g. ``User_10`` read as ``User_1``, emails missing the last character).
    """
    stripped = line.rstrip("\n\r")
    matches = list(_TOKEN.finditer(stripped))
    if not matches:
        return []

    line_end = len(stripped)
    columns: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        name = _NAMED_BY_INDEX[index] if index < len(_NAMED_BY_INDEX) else f"field_{index + 1}"
        field_end = matches[index + 1].start() if index + 1 < len(matches) else line_end
        columns.append({
            "field_name": name,
            "source_start": match.start(),
            "source_end": field_end,
            "target_start": match.start(),
            "target_end": field_end,
            "field_type": "date" if name == "dob" else "text",
        })
    return columns


def merge_layout_columns(
    source_columns: list[dict[str, Any]],
    target_columns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Align source/target layouts by column index (same field order)."""
    count = max(len(source_columns), len(target_columns))
    merged: list[dict[str, Any]] = []
    for index in range(count):
        src = source_columns[index] if index < len(source_columns) else None
        tgt = target_columns[index] if index < len(target_columns) else None
        name = (
            (src or {}).get("field_name")
            or (tgt or {}).get("field_name")
            or f"field_{index + 1}"
        )
        merged.append({
            "field_name": name,
            "source_start": int((src or {}).get("source_start", 0)),
            "source_end": int((src or {}).get("source_end", 0)),
            "target_start": int((tgt or {}).get("target_start", 0)),
            "target_end": int((tgt or {}).get("target_end", 0)),
            "field_type": (src or tgt or {}).get("field_type", "text"),
        })
    return merged


def preview_fixed_width_layout(
    *,
    source_path: str,
    target_path: str,
    max_sample_lines: int = 3,
) -> dict[str, Any]:
    """Read a few lines from each file and infer column slices."""
    from pathlib import Path

    def _first_lines(path: Path, limit: int) -> list[str]:
        lines: list[str] = []
        with path.open(encoding="utf-8", errors="replace") as fp:
            for raw in fp:
                if raw.strip():
                    lines.append(raw)
                if len(lines) >= limit:
                    break
        return lines

    src_path = Path(source_path)
    tgt_path = Path(target_path)
    src_lines = _first_lines(src_path, max_sample_lines)
    tgt_lines = _first_lines(tgt_path, max_sample_lines)
    if not src_lines and not tgt_lines:
        return {"columns": [], "source_sample": "", "target_sample": ""}

    src_cols = infer_columns_from_line(src_lines[0]) if src_lines else []
    tgt_cols = infer_columns_from_line(tgt_lines[0]) if tgt_lines else []
    columns = merge_layout_columns(src_cols, tgt_cols)
    suggested_join = "name" if any(c["field_name"] == "name" for c in columns) else (
        columns[0]["field_name"] if columns else "id"
    )
    return {
        "columns": columns,
        "suggested_join_column": suggested_join,
        "source_sample": src_lines[0].rstrip()[:240] if src_lines else "",
        "target_sample": tgt_lines[0].rstrip()[:240] if tgt_lines else "",
    }
