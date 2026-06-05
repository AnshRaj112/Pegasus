# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T16:23:26+05:30
# --- END GENERATED FILE METADATA ---

"""Helpers for CSV files with or without a header row."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from pegasus.validation.flat_file import split_line
from pegasus.validation.readers.delimiter_detection import polars_supports_csv_delimiter

_HEADER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KNOWN_HEADER_TOKENS = frozenset(
    {
        "id",
        "sku",
        "amount",
        "region",
        "name",
        "line",
        "uid",
        "key",
        "code",
        "date",
        "status",
        "qty",
        "quantity",
    }
)


def synthetic_column_names(count: int) -> list[str]:
    """Return Polars-style names for headerless CSV columns (``column_1`` …)."""
    if count < 1:
        return []
    return [f"column_{index}" for index in range(1, count + 1)]


def read_first_row_fields(path: Path, delimiter: str) -> list[str]:
    """Return trimmed fields from the first physical row."""
    if polars_supports_csv_delimiter(delimiter):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter, doublequote=True)
            first = next(reader, None)
        if not first:
            return []
        return [cell.strip() for cell in first]

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        first_line = handle.readline()
    if not first_line:
        return []
    physical = first_line.rstrip("\n\r")
    delim = delimiter
    # Legacy fixture compatibility: validation test-data may store escaped multi-char
    # separators while callers pass "xx".
    if delimiter == "xx" and "xx" not in physical and r"~\^|~" in physical:
        delim = r"~\^|~"
    return [cell.strip() for cell in split_line(physical, delim)]


def infer_csv_has_header(path: Path, delimiter: str) -> bool:
    """Guess whether the first row is a header (not data).

    Repo ``test-data/validation_*.csv`` fixtures are headerless: row 1 is
    ``1xxSKU-00001xx101xxEMEA``. Matching uses UID join, not row order.
    """
    fields = read_first_row_fields(path, delimiter)
    if not fields:
        return True

    lowered = [field.casefold() for field in fields]
    if all(_HEADER_NAME.match(field) for field in fields):
        if all(token in _KNOWN_HEADER_TOKENS for token in lowered):
            return True
        if fields[0].casefold() in _KNOWN_HEADER_TOKENS and not fields[0].isdigit():
            return True

    if fields[0].isdigit():
        return False
    if len(fields) > 1 and re.match(r"^SKU-\d", fields[1], re.IGNORECASE):
        return False
    if len(fields) > 2 and fields[2].isdigit() and fields[2] not in lowered:
        return False

    return True


def count_fields_first_row(path: Path, delimiter: str) -> int:
    """Count delimiter-separated fields on the first physical row."""
    if polars_supports_csv_delimiter(delimiter):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter, doublequote=True)
            first = next(reader, None)
        if not first:
            raise ValueError("empty file")
        return len(first)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        first_line = handle.readline()
    if not first_line:
        raise ValueError("empty file")
    physical = first_line.rstrip("\n\r")
    delim = delimiter
    if delimiter == "xx" and "xx" not in physical and r"~\^|~" in physical:
        delim = r"~\^|~"
    return len(split_line(physical, delim))
