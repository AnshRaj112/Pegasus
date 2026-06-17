# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:46:02Z
# --- END GENERATED FILE METADATA ---

"""Universal flat-file (delimiter-separated) parsing and schema validation.

Supports any UTF-8 delimiter (multi-character, emoji, control characters) and
RFC 4180-style double-quoted fields so commas (or other delimiter characters)
inside values—e.g. ``"Pune, Maharashtra, 123456"`` or names like
``"Vidit J. Tiwari"``—do not create extra columns.
"""

from __future__ import annotations

import codecs
import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Iterable, TextIO


class FlatFileError(Exception):
    """Base error for flat-file parse/validate failures."""


class EmptyDelimiterError(FlatFileError, ValueError):
    """Raised when the delimiter resolves to an empty string."""


def split_physical_lines(text: str) -> list[str]:
    """Split file text on newline characters only.

    Unlike ``str.splitlines()``, this does **not** treat Unicode line-separator
    code points (e.g. U+001E RECORD SEPARATOR) as row boundaries. Those characters
    may legitimately be used as field delimiters.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized:
        return []
    lines = normalized.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


class ColumnType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    """Per-column validation rule (Unicode-aware regex and length checks)."""

    name: str
    type: ColumnType = ColumnType.STRING
    required: bool = True
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    date_format: str | None = None


@dataclass(slots=True)
class CellValidationError:
    row_number: int
    column: str | None
    value: str
    message: str


@dataclass(slots=True)
class FlatFileParseResult:
    delimiter: str
    headers: list[str]
    rows: list[list[str]]
    expected_column_count: int
    column_count_errors: list[CellValidationError] = field(default_factory=list)
    schema_errors: list[CellValidationError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.column_count_errors and not self.schema_errors


def normalize_delimiter(token: str) -> str:
    """Resolve API/UI delimiter tokens to the actual separator string.

    Supports named tokens (``tab``), escape sequences (``\\t``, ``\\x01``,
    ``\\u200B``), and passes through literal multi-character / emoji delimiters.
    """
    raw = (token or "").strip()
    if not raw:
        raise EmptyDelimiterError("Delimiter must not be empty")

    lowered = raw.lower()
    if lowered in {"tab", "\\t", "\\\\t"}:
        return "\t"

    if "\\" in raw:
        try:
            decoded = codecs.decode(raw, "unicode_escape")
        except UnicodeDecodeError as exc:
            raise FlatFileError(f"Invalid delimiter escape sequence: {raw!r}") from exc
        if not decoded:
            raise EmptyDelimiterError("Delimiter must not be empty after unescaping")
        return decoded

    return raw


def _split_line_respecting_quotes(line: str, delimiter: str, quote_char: str) -> list[str]:
    """Split *line* on *delimiter* only outside RFC 4180 quoted fields.

    Opening *quote_char* starts a quoted field only at a field boundary. A quote
    in the middle of an otherwise unquoted field is kept literally (e.g. ``b"``).
    Inside quoted fields, ``""`` is an escaped literal quote.
    """
    fields: list[str] = []
    buf: list[str] = []
    i = 0
    dlen = len(delimiter)
    n = len(line)

    while True:
        if i >= n:
            if buf or fields:
                fields.append("".join(buf))
            break
        if line[i] == quote_char:
            i += 1
            while i < n:
                ch = line[i]
                if ch == quote_char:
                    if i + 1 < n and line[i + 1] == quote_char:
                        buf.append(quote_char)
                        i += 2
                    elif i + 1 < n and line[i + 1 : i + 1 + dlen] == delimiter:
                        i += 1
                        break
                    elif i + 1 >= n:
                        i += 1
                        break
                    else:
                        buf.append(quote_char)
                        i += 1
                else:
                    buf.append(ch)
                    i += 1
            fields.append("".join(buf))
            buf.clear()
            if i < n and line[i : i + dlen] == delimiter:
                i += dlen
            if i >= n:
                break
            continue
        while i < n:
            if line[i : i + dlen] == delimiter:
                fields.append("".join(buf))
                buf.clear()
                i += dlen
                break
            buf.append(line[i])
            i += 1
        else:
            fields.append("".join(buf))
            buf.clear()
            break
    return fields


def replace_outside_quotes(
    text: str,
    old: str,
    new: str,
    *,
    quote_char: str = '"',
) -> str:
    """Replace *old* with *new* only outside RFC 4180 quoted fields."""
    if not old:
        return text
    out: list[str] = []
    i = 0
    olen = len(old)
    n = len(text)
    at_field_start = True

    while i < n:
        if at_field_start and text[i] == quote_char:
            out.append(quote_char)
            i += 1
            at_field_start = False
            while i < n:
                ch = text[i]
                if ch == quote_char:
                    if i + 1 < n and text[i + 1] == quote_char:
                        out.append(quote_char)
                        out.append(quote_char)
                        i += 2
                    elif i + 1 < n and text[i + 1 : i + 1 + olen] == old:
                        out.append(quote_char)
                        i += 1
                        break
                    elif i + 1 >= n:
                        out.append(quote_char)
                        i += 1
                        break
                    else:
                        out.append(quote_char)
                        i += 1
                else:
                    out.append(ch)
                    i += 1
            at_field_start = True
            continue
        if text[i : i + olen] == old:
            out.append(new)
            i += olen
            at_field_start = True
        else:
            out.append(text[i])
            i += 1
            at_field_start = False
    return "".join(out)


def split_line(
    line: str,
    delimiter: str,
    *,
    quote_char: str = '"',
    respect_quotes: bool = True,
) -> list[str]:
    """Split one physical line into fields (any delimiter length, Unicode-safe).

    When *respect_quotes* is true (default), delimiters inside double-quoted
    fields are ignored. Escaped quotes (``""``) become a single quote in the value.

    Single-character delimiters use the stdlib :mod:`csv` parser (same rules as
    pandas ``read_csv``). Multi-character delimiters use the built-in RFC-style
    state machine in :func:`_split_line_respecting_quotes`.
    """
    if not delimiter:
        raise EmptyDelimiterError("Delimiter must not be empty")
    physical = line.rstrip("\r\n")
    if not respect_quotes or quote_char not in physical:
        return physical.split(delimiter)
    if len(delimiter) == 1 and quote_char == '"':
        try:
            return next(
                csv.reader(
                    [physical],
                    delimiter=delimiter,
                    quotechar=quote_char,
                    doublequote=True,
                )
            )
        except csv.Error:
            return _split_line_respecting_quotes(physical, delimiter, quote_char)
    return _split_line_respecting_quotes(physical, delimiter, quote_char)


def field_count(line: str, delimiter: str, *, quote_char: str = '"') -> int:
    """Number of fields on a line (quote-aware)."""
    return len(split_line(line, delimiter, quote_char=quote_char))


def csv_has_data_rows(path: Path | str, *, encoding: str = "utf-8") -> bool:
    """Return whether a CSV has any data rows when the first line is treated as a header.

    Zero-byte files, whitespace-only files, and header-only files (no non-blank lines
    after the first) return ``False``.
    """
    resolved = Path(path)
    try:
        if resolved.stat().st_size == 0:
            return False
    except OSError:
        return False
    with resolved.open("r", encoding=encoding, errors="replace", newline="") as handle:
        handle.readline()
        while True:
            line = handle.readline()
            if not line:
                return False
            if line.strip():
                return True


def parse_lines(
    lines: Iterable[str],
    delimiter: str,
    *,
    has_header: bool = True,
    strip_fields: bool = False,
    skip_empty_lines: bool = True,
    quote_char: str = '"',
    respect_quotes: bool = True,
) -> FlatFileParseResult:
    """Parse an iterable of text lines into headers and row field lists."""
    delim = normalize_delimiter(delimiter)

    row_iter = list(lines)
    if skip_empty_lines:
        row_iter = [ln for ln in row_iter if ln.strip()]

    if not row_iter:
        return FlatFileParseResult(
            delimiter=delim,
            headers=[],
            rows=[],
            expected_column_count=0,
        )

    def _fields(line: str) -> list[str]:
        parts = split_line(
            line,
            delim,
            quote_char=quote_char,
            respect_quotes=respect_quotes,
        )
        return [p.strip() for p in parts] if strip_fields else parts

    if has_header:
        headers = _fields(row_iter[0])
        data_lines = row_iter[1:]
    else:
        from pegasus.validation.csv_header import synthetic_column_names

        first = _fields(row_iter[0])
        headers = synthetic_column_names(len(first))
        data_lines = row_iter

    expected = len(headers)
    rows: list[list[str]] = []
    column_errors: list[CellValidationError] = []

    for idx, line in enumerate(data_lines, start=2 if has_header else 1):
        fields = _fields(line)
        rows.append(fields)
        if len(fields) != expected:
            column_errors.append(
                CellValidationError(
                    row_number=idx,
                    column=None,
                    value=line.rstrip("\r\n"),
                    message=(
                        f"Expected {expected} column(s), found {len(fields)} "
                        f"(delimiter {delim!r})"
                    ),
                )
            )

    return FlatFileParseResult(
        delimiter=delim,
        headers=headers,
        rows=rows,
        expected_column_count=expected,
        column_count_errors=column_errors,
    )


def parse_file(
    path: Path | str,
    delimiter: str,
    *,
    encoding: str = "utf-8",
    errors: str = "strict",
    has_header: bool = True,
    strip_fields: bool = False,
    skip_empty_lines: bool = True,
    quote_char: str = '"',
    respect_quotes: bool = True,
) -> FlatFileParseResult:
    """Read a UTF-8 (or other encoding) flat file and parse all rows."""
    file_path = Path(path)
    text = file_path.read_text(encoding=encoding, errors=errors)
    return parse_lines(
        split_physical_lines(text),
        delimiter,
        has_header=has_header,
        strip_fields=strip_fields,
        skip_empty_lines=skip_empty_lines,
        quote_char=quote_char,
        respect_quotes=respect_quotes,
    )


def parse_stream(
    stream: TextIO | BinaryIO,
    delimiter: str,
    *,
    encoding: str = "utf-8",
    has_header: bool = True,
    strip_fields: bool = False,
    skip_empty_lines: bool = True,
    quote_char: str = '"',
    respect_quotes: bool = True,
) -> FlatFileParseResult:
    """Parse from an open text stream or binary stream (decoded as UTF-8)."""
    if isinstance(stream, BinaryIO):
        text = stream.read().decode(encoding)
        lines = split_physical_lines(text)
    else:
        lines = split_physical_lines(stream.read())
    return parse_lines(
        lines,
        delimiter,
        has_header=has_header,
        strip_fields=strip_fields,
        skip_empty_lines=skip_empty_lines,
        quote_char=quote_char,
        respect_quotes=respect_quotes,
    )


def _unicode_length(value: str) -> int:
    """Character count in Unicode code points (not grapheme clusters)."""
    return len(value)


def _validate_cell(value: str, rule: ColumnSchema) -> str | None:
    if rule.required and not value.strip():
        return "Value is required"

    if not value.strip() and not rule.required:
        return None

    length = _unicode_length(value)
    if rule.min_length is not None and length < rule.min_length:
        return f"Length {length} is below minimum {rule.min_length}"
    if rule.max_length is not None and length > rule.max_length:
        return f"Length {length} exceeds maximum {rule.max_length}"

    if rule.pattern is not None:
        if not re.fullmatch(rule.pattern, value, flags=re.UNICODE):
            return f"Value does not match pattern {rule.pattern!r}"

    if rule.type is ColumnType.INTEGER:
        try:
            int(value.strip())
        except ValueError:
            return "Expected integer"
    elif rule.type is ColumnType.FLOAT:
        try:
            float(value.strip())
        except ValueError:
            return "Expected float"
    elif rule.type is ColumnType.DATE:
        fmt = rule.date_format or "%Y-%m-%d"
        try:
            datetime.strptime(value.strip(), fmt)
        except ValueError:
            return f"Expected date with format {fmt!r}"

    return None


def validate_schema(
    result: FlatFileParseResult,
    schema: list[ColumnSchema],
    *,
    row_offset: int = 2,
) -> list[CellValidationError]:
    """Apply column schema rules to parsed rows (1-based row numbers in output)."""
    errors: list[CellValidationError] = []
    rules_by_name = {rule.name: rule for rule in schema}

    for row_idx, row in enumerate(result.rows):
        physical_row = row_offset + row_idx
        for col_idx, header in enumerate(result.headers):
            rule = rules_by_name.get(header)
            if rule is None:
                continue
            value = row[col_idx] if col_idx < len(row) else ""
            msg = _validate_cell(value, rule)
            if msg:
                errors.append(
                    CellValidationError(
                        row_number=physical_row,
                        column=header,
                        value=value,
                        message=msg,
                    )
                )
    return errors


def parse_and_validate(
    path: Path | str,
    delimiter: str,
    schema: list[ColumnSchema],
    **parse_kwargs: object,
) -> FlatFileParseResult:
    """Parse a file and attach schema validation errors to the result."""
    result = parse_file(path, delimiter, **parse_kwargs)  # type: ignore[arg-type]
    result.schema_errors = validate_schema(result, schema)
    return result
