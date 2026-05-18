"""Pre-validation analysis for column mapping formats and file footers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl

from pegasus.schemas.validation import ColumnMapping
from pegasus.validation.footer_validation import read_trailing_csv_rows, validate_footer_rows
from pegasus.validation.format_profiles import check_mapping_format
def _read_sample_frame(path: Path, *, delimiter: str, sample_rows: int) -> pl.DataFrame:
    if len(delimiter) > 1:
        pdf = pd.read_csv(
            path,
            sep=re.escape(delimiter),
            engine="python",
            encoding="utf-8",
            nrows=sample_rows,
        )
        return pl.from_pandas(pdf, include_index=False)
    return pl.read_csv(
        path,
        separator=delimiter,
        n_rows=sample_rows,
        infer_schema_length=min(sample_rows, 10_000),
        ignore_errors=True,
    )


def sample_column_values(
    path: Path,
    *,
    delimiter: str,
    columns: list[str],
    sample_rows: int = 500,
) -> dict[str, list[str]]:
    """Read up to *sample_rows* of data and return string values per requested column."""
    if not columns:
        return {}

    frame = _read_sample_frame(path, delimiter=delimiter, sample_rows=sample_rows)

    out: dict[str, list[str]] = {}
    for col in columns:
        if col not in frame.columns:
            out[col] = []
            continue
        series = frame[col].cast(pl.String)
        out[col] = [v if v is not None else "" for v in series.to_list()]
    return out


def analyze_column_mappings(
    *,
    source_path: Path,
    target_path: Path,
    delimiter: str,
    column_mappings: list[ColumnMapping],
    validate_header_formats: bool,
    validate_footers: bool,
    footer_trailing_rows: int,
    sample_rows: int = 500,
) -> dict[str, Any]:
    """Run optional header-format and footer checks."""
    result: dict[str, Any] = {
        "format_checks": [],
        "footer_validation": None,
    }

    if validate_header_formats and column_mappings:
        source_cols = [m.source_column for m in column_mappings]
        target_cols = [m.target_column for m in column_mappings]
        src_samples = sample_column_values(
            source_path, delimiter=delimiter, columns=source_cols, sample_rows=sample_rows
        )
        tgt_samples = sample_column_values(
            target_path, delimiter=delimiter, columns=target_cols, sample_rows=sample_rows
        )
        checks: list[dict[str, Any]] = []
        for mapping in column_mappings:
            checks.append(
                check_mapping_format(
                    source_column=mapping.source_column,
                    target_column=mapping.target_column,
                    source_values=src_samples.get(mapping.source_column, []),
                    target_values=tgt_samples.get(mapping.target_column, []),
                )
            )
        result["format_checks"] = checks

    if validate_footers and footer_trailing_rows > 0:
        src_footer = read_trailing_csv_rows(
            source_path, delimiter=delimiter, trailing_rows=footer_trailing_rows
        )
        tgt_footer = read_trailing_csv_rows(
            target_path, delimiter=delimiter, trailing_rows=footer_trailing_rows
        )
        result["footer_validation"] = validate_footer_rows(src_footer, tgt_footer)

    return result
