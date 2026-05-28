"""Pre-validation analysis for column mapping formats and file footers."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl

from pegasus.schemas.validation import ColumnMapping
from pegasus.validation.footer_validation import read_trailing_csv_rows, validate_footer_rows
from pegasus.validation.format_profiles import check_mapping_format
from pegasus.validation.readers.delimiter_detection import polars_supports_csv_delimiter


def _read_sample_frame(
    path: Path,
    *,
    delimiter: str,
    sample_rows: int,
    has_header: bool = True,
) -> pl.DataFrame:
    if not polars_supports_csv_delimiter(delimiter):
        pdf = pd.read_csv(
            path,
            sep=re.escape(delimiter),
            engine="python",
            encoding="utf-8",
            nrows=sample_rows,
            header=0 if has_header else None,
            quotechar='"',
            doublequote=True,
        )
        if not has_header:
            pdf.columns = [f"column_{index}" for index in range(1, len(pdf.columns) + 1)]
        return pl.from_pandas(pdf, include_index=False)
    return pl.read_csv(
        path,
        separator=delimiter,
        n_rows=sample_rows,
        has_header=has_header,
        infer_schema_length=min(sample_rows, 10_000),
        ignore_errors=True,
    )


def sample_column_values(
    path: Path,
    *,
    delimiter: str,
    columns: list[str],
    sample_rows: int = 500,
    has_header: bool = True,
) -> dict[str, list[str]]:
    """Read up to *sample_rows* of data and return string values per requested column."""
    if not columns:
        return {}

    frame = _read_sample_frame(
        path,
        delimiter=delimiter,
        sample_rows=sample_rows,
        has_header=has_header,
    )

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
    has_header: bool = True,
    header_leading_rows: int = 0,
    footer_validation_source_path: Path | None = None,
    footer_validation_target_path: Path | None = None,
) -> dict[str, Any]:
    """Run optional header-format and footer checks."""
    result: dict[str, Any] = {
        "format_checks": [],
        "footer_validation": None,
    }

    source_for_samples = source_path
    target_for_samples = target_path
    cleanup_paths: list[Path] = []
    if header_leading_rows > 0:
        source_for_samples, src_tmp = _trim_csv_rows(source_path, header_leading_rows)
        target_for_samples, tgt_tmp = _trim_csv_rows(target_path, header_leading_rows)
        cleanup_paths.extend([src_tmp, tgt_tmp])

    if validate_header_formats and column_mappings:
        source_cols = [m.source_column for m in column_mappings]
        target_cols = [m.target_column for m in column_mappings]
        src_samples = sample_column_values(
            source_for_samples,
            delimiter=delimiter,
            columns=source_cols,
            sample_rows=sample_rows,
            has_header=has_header,
        )
        tgt_samples = sample_column_values(
            target_for_samples,
            delimiter=delimiter,
            columns=target_cols,
            sample_rows=sample_rows,
            has_header=has_header,
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
            footer_validation_source_path or source_path, delimiter=delimiter, trailing_rows=footer_trailing_rows
        )
        tgt_footer = read_trailing_csv_rows(
            footer_validation_target_path or target_path, delimiter=delimiter, trailing_rows=footer_trailing_rows
        )
        result["footer_validation"] = validate_footer_rows(src_footer, tgt_footer)

    for p in cleanup_paths:
        p.unlink(missing_ok=True)
    return result


def _trim_csv_rows(path: Path, header_leading_rows: int) -> tuple[Path, Path]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    kept = lines[min(header_leading_rows, len(lines)):]
    fd, tmp_path = tempfile.mkstemp(prefix="pegasus_mapping_trim_", suffix=".csv")
    Path(tmp_path).write_text("\n".join(kept), encoding="utf-8")
    tmp = Path(tmp_path)
    return tmp, tmp
