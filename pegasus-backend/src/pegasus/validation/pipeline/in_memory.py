"""In-memory reconciliation for datasets that fit in RAM (fast path)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import polars as pl

from pegasus.validation.adapters.base import TabularSourceAdapter
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.result import ColumnDifference, MismatchSample, PipelineResult
from pegasus.validation.readers.pyarrow_io import (
    pyarrow_supports_delimiter,
    read_csv_table,
    read_orc_table,
    read_parquet_table,
    table_to_polars,
)


def _canonical(value: Any) -> str:
    if value is None:
        return "__NULL__"
    text = str(value).strip()
    if text.lower() in ("", "null", "none", "na", "n/a"):
        return "__NULL__"
    return text


def _identity_key_from_row(row: dict[str, Any], columns: list[str]) -> str:
    return "|".join(_canonical(row.get(c)) for c in columns)


def _should_use_in_memory(
    source_path: Path,
    target_path: Path,
    *,
    memory_budget_bytes: int,
    max_file_bytes: int = 512 * 1024 * 1024,
) -> bool:
    try:
        file_bytes = source_path.stat().st_size + target_path.stat().st_size
    except OSError:
        return False
    if file_bytes > max_file_bytes:
        return False
    # Two frames plus join overhead — keep a conservative headroom factor.
    return file_bytes * 4 < int(memory_budget_bytes * 0.65)


def _load_delimited_frame(
    path: Path,
    *,
    delimiter: str,
    has_header: bool = True,
    skip_rows: int = 0,
) -> pl.DataFrame:
    if pyarrow_supports_delimiter(delimiter):
        return table_to_polars(
            read_csv_table(
                path,
                delimiter=delimiter,
                has_header=has_header,
                skip_rows=skip_rows,
            )
        )

    adapter = FileDelimitedAdapter(
        path,
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=skip_rows,
    )
    rows: list[dict[str, Any]] = []
    for chunk in adapter.stream_records(100_000):
        rows.extend(chunk)
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def _load_frame(adapter: TabularSourceAdapter) -> pl.DataFrame | None:
    path = Path(adapter.path)
    if isinstance(adapter, FileDelimitedAdapter):
        return _load_delimited_frame(
            path,
            delimiter=adapter._delimiter,
            has_header=adapter._has_header,
            skip_rows=adapter._skip_rows,
        )
    fmt = getattr(adapter, "_file_format", "parquet")
    if fmt in ("parquet", "pq"):
        return table_to_polars(read_parquet_table(path))
    if fmt == "orc":
        return table_to_polars(read_orc_table(path))
    if fmt in ("excel", "xlsx", "xls"):
        return pl.read_excel(path)
    return None


def _fingerprint_expr(columns: list[str], *, suffix: str = "") -> pl.Expr:
    parts = [
        pl.col(f"{column}{suffix}").cast(pl.Utf8).fill_null("__NULL__").str.strip_chars()
        for column in columns
    ]
    if not parts:
        return pl.lit("").alias("_fp")
    return pl.concat_str(parts, separator="\x1f").alias("_fp")


def try_in_memory_reconcile(
    source: TabularSourceAdapter,
    target: TabularSourceAdapter,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    memory_budget_bytes: int,
    enable_column_drilldown: bool,
    sample_limit: int = 1000,
) -> PipelineResult | None:
    """Return a :class:`PipelineResult` when both sides fit in memory; else ``None``."""
    source_path = Path(source.path)
    target_path = Path(target.path)
    if not _should_use_in_memory(source_path, target_path, memory_budget_bytes=memory_budget_bytes):
        return None

    t0 = time.perf_counter()
    try:
        src = _load_frame(source)
        tgt = _load_frame(target)
    except Exception:
        return None
    if src is None or tgt is None:
        return None

    src = src.with_columns(_fingerprint_expr(compare_columns).alias("_fp"))
    tgt = tgt.with_columns(_fingerprint_expr(compare_columns).alias("_fp"))

    src_keys = src.select([*identity_columns, *compare_columns, "_fp"])
    tgt_keys = tgt.select([*identity_columns, *compare_columns, "_fp"])

    missing_df = src_keys.join(
        tgt_keys.select(identity_columns),
        on=identity_columns,
        how="anti",
    )
    extra_df = tgt_keys.join(
        src_keys.select(identity_columns),
        on=identity_columns,
        how="anti",
    )

    inner = src_keys.join(
        tgt_keys,
        on=identity_columns,
        how="inner",
        suffix="_tgt",
    )
    changed_df = inner.filter(pl.col("_fp") != pl.col("_fp_tgt"))
    matching = inner.height - changed_df.height

    samples: list[MismatchSample] = []

    def _append_samples(frame: pl.DataFrame, mtype: str, *, with_cols: bool = False) -> None:
        nonlocal samples
        if len(samples) >= sample_limit or frame.is_empty():
            return
        take = min(sample_limit - len(samples), frame.height)
        for row in frame.head(take).iter_rows(named=True):
            key = _identity_key_from_row(row, identity_columns)
            if mtype == "changed" and with_cols:
                col_diffs: list[ColumnDifference] = []
                for col in compare_columns:
                    sv = _canonical(row.get(col))
                    tv = _canonical(row.get(f"{col}_tgt"))
                    if sv != tv:
                        col_diffs.append(ColumnDifference(col, sv, tv))
                samples.append(MismatchSample(key, mtype, col_diffs))
            else:
                samples.append(MismatchSample(key, mtype))

    _append_samples(missing_df, "missing")
    _append_samples(extra_df, "extra")
    _append_samples(changed_df, "changed", with_cols=enable_column_drilldown)

    elapsed = time.perf_counter() - t0
    return PipelineResult(
        schema_valid=set(src.columns) == set(tgt.columns),
        source_row_count=src.height,
        target_row_count=tgt.height,
        row_count_match=src.height == tgt.height,
        missing_count=missing_df.height,
        extra_count=extra_df.height,
        changed_count=changed_df.height,
        matching_count=matching,
        partitions_processed=0,
        mismatched_partitions=0,
        sample_mismatches=samples,
        compared_columns=list(compare_columns),
        execution_seconds=elapsed,
    )
