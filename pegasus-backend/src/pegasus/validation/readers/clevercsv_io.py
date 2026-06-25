# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T11:38:03Z
# --- END GENERATED FILE METADATA ---

"""Fast multi-character delimiter CSV load via clevercsv."""

from __future__ import annotations

import io
from typing import Any

import polars as pl

from pegasus.validation.flat_file import parse_lines, split_physical_lines
from pegasus.validation.readers.multichar_csv import can_use_fast_multichar_load, load_multichar_csv_fast


def clevercsv_to_polars(
    source: Any,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
) -> pl.DataFrame | None:
    """Return a Polars frame when clevercsv can parse *delimiter*, else ``None``."""
    if not delimiter:
        return None
    try:
        import clevercsv
    except ImportError:
        return None

    payload = source.read()
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", errors="replace")
    else:
        text = payload

    if skip_rows:
        lines = text.splitlines()
        text = "\n".join(lines[skip_rows:])

    try:
        pd_frame = clevercsv.read_csv(
            io.StringIO(text),
            delimiter=delimiter,
            header=0 if has_header else None,
        )
        if pd_frame is None or pd_frame.empty:
            return pl.DataFrame()
        return pl.from_pandas(pd_frame, rechunk=False)
    except Exception:
        return None


def flat_file_to_polars(
    source: Any,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
    path: Path | None = None,
) -> pl.DataFrame:
    """Fallback flat-file parser when clevercsv is unavailable or fails."""
    if path is not None and can_use_fast_multichar_load(path, delimiter):
        return load_multichar_csv_fast(path, delimiter=delimiter, has_header=has_header, skip_rows=skip_rows)

    if hasattr(source, "read"):
        payload = source.read()
        text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    else:
        text = source
    if skip_rows:
        lines = text.splitlines()
        text = "\n".join(lines[skip_rows:])
    parsed = parse_lines(split_physical_lines(text), delimiter, has_header=has_header)
    if not parsed.rows:
        return pl.DataFrame()
    columns = parsed.headers or [f"col_{i}" for i in range(len(parsed.rows[0]))]
    column_data = {
        name: [(row[i] if i < len(row) else None) for row in parsed.rows]
        for i, name in enumerate(columns)
    }
    return pl.DataFrame(column_data)
