"""Compare non-date portions of fixed-width lines as separate fields."""

from __future__ import annotations

import re

# Common Pegasus sample layout (id, name, email) before the DOB slice.
_OUTER_FIELD_NAMES: tuple[str, ...] = ("id", "name", "email", "field_4", "field_5", "field_6")

# Default join key (name) and value slices for date-only / unsorted target runs.
DEFAULT_JOIN_KEY_COLUMN = "name"
DEFAULT_JOIN_SOURCE_START = 8
DEFAULT_JOIN_SOURCE_END = 28
DEFAULT_JOIN_TARGET_START = 8
DEFAULT_JOIN_TARGET_END = 28

# Value columns compared after rows are matched on name (id may differ).
DEFAULT_VALUE_FIELD_SLICES: tuple[tuple[str, int, int], ...] = (
    ("id", 0, 5),
    ("email", 28, 58),
)


def diff_outer_field_mismatches(src_outer: str, tgt_outer: str) -> list[tuple[str, str, str]]:
    """Return ``(column_name, source_value, target_value)`` for each differing field.

    Whitespace-separated values are compared as individual columns (``id``, ``name``, …).
    When the outer region is a single contiguous span, only the differing substring is
    returned under ``content``.
    """
    src = src_outer.rstrip("\n\r")
    tgt = tgt_outer.rstrip("\n\r")
    if src == tgt:
        return []

    src_tokens = re.findall(r"\S+", src)
    tgt_tokens = re.findall(r"\S+", tgt)
    if len(src_tokens) > 1 or len(tgt_tokens) > 1:
        mismatches: list[tuple[str, str, str]] = []
        for index in range(max(len(src_tokens), len(tgt_tokens))):
            source_val = src_tokens[index] if index < len(src_tokens) else ""
            target_val = tgt_tokens[index] if index < len(tgt_tokens) else ""
            if source_val == target_val:
                continue
            if index < len(_OUTER_FIELD_NAMES):
                column_name = _OUTER_FIELD_NAMES[index]
            else:
                column_name = f"field_{index + 1}"
            mismatches.append((column_name, source_val, target_val))
        return mismatches

    start = 0
    limit = min(len(src), len(tgt))
    while start < limit and src[start] == tgt[start]:
        start += 1
    end = 0
    while end < limit - start and src[len(src) - 1 - end] == tgt[len(tgt) - 1 - end]:
        end += 1
    source_val = src[start : len(src) - end] if end else src[start:]
    target_val = tgt[start : len(tgt) - end] if end else tgt[start:]
    if not source_val and not target_val:
        source_val = src
        target_val = tgt
    return [("content", source_val, target_val)]


def compare_fixed_width_slices(
    src_line: str,
    tgt_line: str,
    fields: tuple[tuple[str, int, int], ...],
) -> list[tuple[str, str, str]]:
    """Return per-column diffs for fixed start/end slices on both lines."""
    mismatches: list[tuple[str, str, str]] = []
    for column_name, start, end in fields:
        if end <= start:
            continue
        src_val = src_line[start:end].strip() if len(src_line) >= end else src_line[start:].strip()
        tgt_val = tgt_line[start:end].strip() if len(tgt_line) >= end else tgt_line[start:].strip()
        if src_val == tgt_val:
            continue
        mismatches.append((column_name, src_val, tgt_val))
    return mismatches
