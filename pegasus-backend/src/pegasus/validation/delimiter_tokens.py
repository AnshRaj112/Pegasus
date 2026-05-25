"""Delimiter tokens stored on validation_runs (VARCHAR(8) limit)."""

from __future__ import annotations

# Fixed-width runs are not CSV-delimited; this token fits validation_runs.delimiter.
FIXED_WIDTH_DELIMITER = "fixed"
JSON_DELIMITER = "json"

_FIXED_WIDTH_ALIASES = frozenset({"fixed", "fixed-width", "fixed_width"})
_JSON_ALIASES = frozenset({"json"})


def is_fixed_width_delimiter(delimiter: str | None) -> bool:
    """Return True when delimiter denotes fixed-width (not CSV) validation."""
    return (delimiter or "").strip().lower() in _FIXED_WIDTH_ALIASES


def is_json_delimiter(delimiter: str | None) -> bool:
    """Return True when delimiter denotes whole-document JSON validation."""
    return (delimiter or "").strip().lower() in _JSON_ALIASES


def normalize_delimiter_for_storage(delimiter: str | None) -> str:
    """Map API/UI aliases to a value that fits validation_runs.delimiter (max 8 chars)."""
    token = (delimiter or "").strip()
    if is_fixed_width_delimiter(token):
        return FIXED_WIDTH_DELIMITER
    if is_json_delimiter(token):
        return JSON_DELIMITER
    if not token:
        return ","
    if len(token) > 8:
        raise ValueError(f"Delimiter {token!r} exceeds 8 characters")
    return token
