"""Structural CSV checks before Polars/pandas ingestion.

Uses the stdlib :mod:`csv` parser for single-character delimiters (RFC 4180 record
boundaries, including embedded newlines in quoted fields). Multi-character
delimiters use the quote-aware :func:`pegasus.validation.flat_file.split_line`
on physical lines (same constraints as multichar spill).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from pegasus.validation.flat_file import split_line
from pegasus.validation.readers.delimiter_detection import polars_supports_csv_delimiter

logger = logging.getLogger(__name__)

GZIP_MAGIC = b"\x1f\x8b"
UTF16_LE_BOM = b"\xff\xfe"
UTF16_BE_BOM = b"\xfe\xff"
UTF8_BOM = b"\xef\xbb\xbf"

# Bound row scans so multi-million-row files stay predictable.
_DEFAULT_MAX_ROWS_TO_SCAN = 50_000


class CsvPreflightError(ValueError):
    """CSV structure is invalid for validation."""


def _read_prefix(path: Path, n: int = 8) -> bytes:
    with path.open("rb") as fh:
        return fh.read(n)


def _detect_binary_or_wrong_encoding(prefix: bytes, *, label: str) -> None:
    if prefix.startswith(GZIP_MAGIC):
        raise CsvPreflightError(
            f"{label}: file looks gzip-compressed (not plain CSV). Decompress before validating."
        )
    if prefix.startswith(UTF16_LE_BOM) or prefix.startswith(UTF16_BE_BOM):
        raise CsvPreflightError(
            f"{label}: UTF-16 byte order mark detected; save the file as UTF-8 before validating."
        )
    if prefix == UTF8_BOM:
        raise CsvPreflightError(f"{label}: file contains only a UTF-8 BOM and no CSV content.")


def _preflight_single_char(
    path: Path,
    delimiter: str,
    *,
    label: str,
    max_rows_to_scan: int,
) -> None:
    errors: list[str] = []
    row_number = 0
    expected_cols: int | None = None
    header_names: list[str] | None = None

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter, doublequote=True)
            for row in reader:
                row_number += 1
                if row_number > max_rows_to_scan + 1:
                    break

                if row_number == 1:
                    header_names = [c.strip() for c in row]
                    if not any(header_names):
                        raise CsvPreflightError(f"{label}: missing or empty header row.")
                    expected_cols = len(header_names)
                    dupes = [name for name in header_names if header_names.count(name) > 1]
                    if dupes:
                        unique_dupes = sorted(set(dupes))
                        errors.append(
                            f"{label}: duplicate header name(s): {', '.join(unique_dupes)!r}."
                        )
                    continue

                if not row or (len(row) == 1 and row[0] == ""):
                    errors.append(f"{label}: row {row_number} is empty.")
                    if len(errors) >= 5:
                        break
                    continue

                if expected_cols is not None and len(row) != expected_cols:
                    errors.append(
                        f"{label}: row {row_number} has {len(row)} field(s), "
                        f"expected {expected_cols} (header has {expected_cols} column(s))."
                    )
                    if len(errors) >= 5:
                        break
    except csv.Error as exc:
        raise CsvPreflightError(f"{label}: malformed CSV near row {row_number}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise CsvPreflightError(
            f"{label}: invalid UTF-8 byte sequence ({exc}). "
            "Re-save the file as UTF-8 or use a UTF-8-clean export."
        ) from exc

    if errors:
        extra = ""
        if row_number > max_rows_to_scan:
            extra = f" (checked first {max_rows_to_scan} data rows)"
        raise CsvPreflightError("\n".join(errors) + extra)


def _preflight_multichar(
    path: Path,
    delimiter: str,
    *,
    label: str,
    max_rows_to_scan: int,
) -> None:
    from pegasus.validation.flat_file import split_physical_lines

    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvPreflightError(
            f"{label}: invalid UTF-8 byte sequence ({exc}). "
            "Re-save the file as UTF-8 or use a UTF-8-clean export."
        ) from exc

    lines = split_physical_lines(text)
    if not lines:
        raise CsvPreflightError(f"{label}: file is empty.")

    errors: list[str] = []
    headers = [c.strip() for c in split_line(lines[0], delimiter)]
    if not headers or headers == [""]:
        raise CsvPreflightError(f"{label}: missing or empty header row.")
    expected = len(headers)

    for idx, line in enumerate(lines[1:], start=2):
        if idx > max_rows_to_scan + 1:
            break
        if not line.strip():
            errors.append(f"{label}: row {idx} is empty.")
            if len(errors) >= 5:
                break
            continue
        fields = split_line(line, delimiter)
        if len(fields) != expected:
            errors.append(
                f"{label}: row {idx} has {len(fields)} field(s), expected {expected}."
            )
            if len(errors) >= 5:
                break

    if errors:
        raise CsvPreflightError("\n".join(errors))


def preflight_csv_structure(
    path: Path,
    delimiter: str,
    *,
    label: str | None = None,
    max_rows_to_scan: int = _DEFAULT_MAX_ROWS_TO_SCAN,
) -> None:
    """Validate basic CSV structure; raise :class:`CsvPreflightError` on failure."""
    resolved = Path(path)
    tag = label or resolved.name

    if resolved.stat().st_size == 0:
        raise CsvPreflightError(f"{tag}: empty input file.")

    prefix = _read_prefix(resolved)
    _detect_binary_or_wrong_encoding(prefix, label=tag)

    if polars_supports_csv_delimiter(delimiter):
        _preflight_single_char(
            resolved,
            delimiter,
            label=tag,
            max_rows_to_scan=max_rows_to_scan,
        )
    else:
        _preflight_multichar(
            resolved,
            delimiter,
            label=tag,
            max_rows_to_scan=max_rows_to_scan,
        )

    logger.debug("CSV preflight passed path=%s delimiter=%r", resolved.name, delimiter)
