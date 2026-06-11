# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-10T11:49:33Z
# --- END GENERATED FILE METADATA ---

"""Column header preview and auto-mapping for the mapping UI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import polars as pl

from pegasus.validation.adapters.file_columnar import FileColumnarAdapter
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.csv_header import infer_csv_has_header
from pegasus.validation.delimited_sample import read_delimited_sample_frame
from pegasus.validation.delimiter_resolve import resolve_delimiter_for_paths
from pegasus.validation.file_format import infer_file_format_from_path, is_columnar_format, normalize_file_format

_MAPPING_PREVIEW_SAMPLE_ROWS = 6


def normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.casefold())


def auto_map_columns(source_columns: list[str], target_columns: list[str]) -> list[dict[str, str]]:
    target_by_norm = {normalize_column_name(c): c for c in target_columns}
    auto: list[dict[str, str]] = []
    seen_targets: set[str] = set()
    for source in source_columns:
        target = target_by_norm.get(normalize_column_name(source))
        if target is None or target in seen_targets:
            continue
        auto.append({"source_column": source, "target_column": target})
        seen_targets.add(target)
    return auto


def _read_columnar_sample(path: Path, file_format: str, sample_rows: int) -> pl.DataFrame:
    fmt = normalize_file_format(file_format)
    if fmt == "parquet":
        return pl.read_parquet(path).head(sample_rows)
    if fmt == "orc":
        return pl.read_orc(path).head(sample_rows)
    if fmt == "avro":
        adapter = FileColumnarAdapter(path, file_format="avro")
        rows: list[dict[str, Any]] = []
        for batch in adapter.stream_records(sample_rows):
            rows.extend(batch)
            if len(rows) >= sample_rows:
                break
        return pl.DataFrame(rows[:sample_rows]) if rows else pl.DataFrame()
    if fmt == "excel":
        return pl.read_excel(path).head(sample_rows)
    return pl.read_parquet(path).head(sample_rows)


def _sample_column_values(frame: pl.DataFrame, columns: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for col in columns:
        if col not in frame.columns:
            out[col] = []
            continue
        out[col] = [v if v is not None else "" for v in frame[col].cast(pl.String).to_list()]
    return out


def _sample_delimited_frame(
    adapter: FileDelimitedAdapter | GcsDelimitedAdapter,
    *,
    sample_rows: int,
) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for chunk in adapter.stream_records(sample_rows):
        rows.extend(chunk)
        if len(rows) >= sample_rows:
            break
    return pl.DataFrame(rows[:sample_rows]) if rows else pl.DataFrame()


def build_column_preview_from_adapters(
    *,
    source: FileDelimitedAdapter | GcsDelimitedAdapter,
    target: FileDelimitedAdapter | GcsDelimitedAdapter,
    uid_column: str,
    resolved_delimiter: str,
    has_header: bool = True,
    file_format: str = "csv",
) -> dict[str, Any]:
    """Return headers and sample values using streaming adapters (local or GCS)."""
    uid = uid_column.strip()
    sample_rows = _MAPPING_PREVIEW_SAMPLE_ROWS
    source_columns = source.get_schema().column_names
    target_columns = target.get_schema().column_names
    inferred_has_header = None
    if isinstance(source.path, Path) and source.path.exists() and isinstance(target.path, Path) and target.path.exists():
        inferred_has_header = infer_csv_has_header(source.path, resolved_delimiter) and infer_csv_has_header(
            target.path, resolved_delimiter
        )
    source_frame = _sample_delimited_frame(source, sample_rows=sample_rows)
    target_frame = _sample_delimited_frame(target, sample_rows=sample_rows)

    compare_columns = [c for c in source_columns if c != uid]
    compare_targets = [c for c in target_columns if c != uid]
    auto_mappings = auto_map_columns(compare_columns, compare_targets)
    matched_sources = {m["source_column"] for m in auto_mappings}
    matched_targets = {m["target_column"] for m in auto_mappings}

    return {
        "source_columns": source_columns,
        "target_columns": target_columns,
        "compare_columns": compare_columns,
        "auto_mappings": auto_mappings,
        "unmatched_source_columns": [c for c in source_columns if c not in matched_sources],
        "unmatched_target_columns": [c for c in target_columns if c not in matched_targets],
        "delimiter": resolved_delimiter,
        "has_header": has_header,
        "inferred_has_header": inferred_has_header,
        "source_samples": _sample_column_values(source_frame, source_columns),
        "target_samples": _sample_column_values(target_frame, target_columns),
        "sample_row_count": sample_rows,
        "file_format": file_format,
    }


def build_column_preview(
    *,
    source_path: Path,
    target_path: Path,
    uid_column: str,
    delimiter: str = "auto",
    has_header: bool = True,
    header_leading_rows: int = 0,
    file_format: str | None = None,
) -> dict[str, Any]:
    """Return source/target headers, auto mappings, and sample values for the UI."""
    uid = uid_column.strip()
    src_fmt = infer_file_format_from_path(source_path, file_format)
    tgt_fmt = infer_file_format_from_path(target_path, file_format)
    if src_fmt != tgt_fmt:
        raise ValueError(f"Source format ({src_fmt}) and target format ({tgt_fmt}) must match")

    sample_rows = _MAPPING_PREVIEW_SAMPLE_ROWS
    columnar = is_columnar_format(src_fmt)

    if columnar:
        src_adapter = FileColumnarAdapter(source_path, file_format=src_fmt)
        tgt_adapter = FileColumnarAdapter(target_path, file_format=src_fmt)
        source_columns = src_adapter.get_schema().column_names
        target_columns = tgt_adapter.get_schema().column_names
        resolved_delimiter = src_fmt
        inferred_has_header = None
        source_frame = _read_columnar_sample(source_path, src_fmt, sample_rows)
        target_frame = _read_columnar_sample(target_path, src_fmt, sample_rows)
    else:
        try:
            resolved_delimiter = resolve_delimiter_for_paths(delimiter, source_path, target_path)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        src_adapter = FileDelimitedAdapter(
            source_path,
            delimiter=resolved_delimiter,
            has_header=has_header,
            skip_rows=header_leading_rows,
        )
        tgt_adapter = FileDelimitedAdapter(
            target_path,
            delimiter=resolved_delimiter,
            has_header=has_header,
            skip_rows=header_leading_rows,
        )
        source_columns = src_adapter.get_schema().column_names
        target_columns = tgt_adapter.get_schema().column_names
        inferred_has_header = infer_csv_has_header(source_path, resolved_delimiter) and infer_csv_has_header(
            target_path, resolved_delimiter
        )
        source_frame = read_delimited_sample_frame(
            source_path,
            delimiter=resolved_delimiter,
            sample_rows=sample_rows,
            has_header=has_header,
            header_leading_rows=header_leading_rows,
        )
        target_frame = read_delimited_sample_frame(
            target_path,
            delimiter=resolved_delimiter,
            sample_rows=sample_rows,
            has_header=has_header,
            header_leading_rows=header_leading_rows,
        )

    compare_columns = [c for c in source_columns if c != uid]
    compare_targets = [c for c in target_columns if c != uid]
    auto_mappings = auto_map_columns(compare_columns, compare_targets)
    matched_sources = {m["source_column"] for m in auto_mappings}
    matched_targets = {m["target_column"] for m in auto_mappings}

    return {
        "source_columns": source_columns,
        "target_columns": target_columns,
        "compare_columns": compare_columns,
        "auto_mappings": auto_mappings,
        "unmatched_source_columns": [c for c in source_columns if c not in matched_sources],
        "unmatched_target_columns": [c for c in target_columns if c not in matched_targets],
        "delimiter": resolved_delimiter,
        "has_header": has_header,
        "inferred_has_header": inferred_has_header,
        "source_samples": _sample_column_values(source_frame, source_columns),
        "target_samples": _sample_column_values(target_frame, target_columns),
        "sample_row_count": sample_rows,
        "file_format": src_fmt,
    }
