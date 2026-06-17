# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:46:02Z
# --- END GENERATED FILE METADATA ---

"""Read bounded delimited samples for column preview and analysis."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.readers.pyarrow_io import pyarrow_supports_delimiter, read_csv_table, table_to_polars


def read_delimited_sample_frame(
    path: Path,
    *,
    delimiter: str,
    sample_rows: int,
    has_header: bool = True,
    header_leading_rows: int = 0,
) -> pl.DataFrame:
    """Load up to *sample_rows* using PyArrow (single-byte) or flat-file fallback."""
    if pyarrow_supports_delimiter(delimiter):
        table = read_csv_table(
            path,
            delimiter=delimiter,
            has_header=has_header,
            skip_rows=header_leading_rows,
            max_rows=sample_rows,
        )
        return table_to_polars(table)

    adapter = FileDelimitedAdapter(
        path,
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=header_leading_rows,
    )
    rows: list[dict] = []
    for chunk in adapter.stream_records(sample_rows):
        rows.extend(chunk)
        if len(rows) >= sample_rows:
            break
    return pl.DataFrame(rows[:sample_rows]) if rows else pl.DataFrame()
