# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Delimiter tokens stored on validation_runs (VARCHAR(8) limit)."""

from __future__ import annotations

FIXED_WIDTH_DELIMITER = "fixed"
JSON_DELIMITER = "json"

_FIXED_WIDTH_ALIASES = frozenset({"fixed", "fixed-width", "fixed_width"})
_JSON_ALIASES = frozenset({"json"})


def normalize_delimiter_for_storage(delimiter: str | None) -> str:
    """Map API/UI aliases to a value that fits validation_runs.delimiter (max 8 chars)."""
    token = (delimiter or "").strip().lower()
    if token in _FIXED_WIDTH_ALIASES:
        return FIXED_WIDTH_DELIMITER
    if token in _JSON_ALIASES:
        return JSON_DELIMITER
    if not token:
        return ","
    if len(token) > 8:
        raise ValueError(f"Delimiter {token!r} exceeds 8 characters")
    return delimiter.strip() if delimiter else ","
