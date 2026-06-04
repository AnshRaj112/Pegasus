# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T12:06:25+05:30
# --- END GENERATED FILE METADATA ---

"""In-memory reconciliation for datasets that fit in RAM (fast path)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any

import polars as pl

from pegasus.validation.adapters.base import TabularSourceAdapter
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter

_HEADERLESS_ADAPTER_TYPES = frozenset({"FileDelimitedAdapter", "GcsDelimitedAdapter"})
from pegasus.validation.flat_file import parse_lines, split_physical_lines
from pegasus.validation.pipeline.result import ColumnDifference, MismatchSample, PipelineResult
from pegasus.validation.readers.pyarrow_io import (
    pyarrow_supports_delimiter,
    read_csv_binary,
    read_csv_bytes,
    read_csv_table,
    read_orc_table,
    read_parquet_table,
    table_to_polars,
)

_DEFAULT_AUTO_IN_MEMORY_MAX_BYTES = 64 * 1024 * 1024


def _canonical(value: Any) -> str:
    if value is None:
        return "__NULL__"
    text = str(value).strip()
    if text.lower() in ("", "null", "none", "na", "n/a"):
        return "__NULL__"
    return text


def _identity_key_from_row(row: dict[str, Any], columns: list[str]) -> str:
    return "|".join(_canonical(row.get(c)) for c in columns)


def _adapter_size_bytes(adapter: TabularSourceAdapter) -> int | None:
    getter = getattr(adapter, "get_size_bytes", None)
    if callable(getter):
        try:
            return int(getter())
        except (OSError, ValueError):
            return None
    path = Path(getattr(adapter, "path", ""))
    try:
        return path.stat().st_size
    except OSError:
        return None


def _should_use_in_memory(
    source: TabularSourceAdapter,
    target: TabularSourceAdapter,
    *,
    memory_budget_bytes: int,
    max_file_bytes: int = 512 * 1024 * 1024,
) -> bool:
    source_bytes = _adapter_size_bytes(source)
    target_bytes = _adapter_size_bytes(target)
    if source_bytes is None or target_bytes is None:
        return False
    file_bytes = source_bytes + target_bytes
    if file_bytes > max_file_bytes:
        return False
    return file_bytes * 4 < int(memory_budget_bytes * 0.65)


def should_try_in_memory_reconcile(
    *,
    enable_in_memory_reconcile: bool,
    auto_in_memory_max_bytes: int,
    source_bytes: int,
    target_bytes: int,
) -> bool:
    """Return whether to attempt the Polars in-memory fast path."""
    if enable_in_memory_reconcile:
        return True
    return source_bytes + target_bytes <= auto_in_memory_max_bytes


def _headerless_column_names(adapter: TabularSourceAdapter) -> list[str] | None:
    if type(adapter).__name__ not in _HEADERLESS_ADAPTER_TYPES:
        return None
    if getattr(adapter, "_has_header", True):
        return None
    getter = getattr(adapter, "get_schema", None)
    if not callable(getter):
        return None
    return list(getter().column_names)


def _align_frame_to_schema(frame: pl.DataFrame, adapter: TabularSourceAdapter) -> pl.DataFrame:
    """Match loaded column names to the adapter schema (streaming path uses the same names)."""
    getter = getattr(adapter, "get_schema", None)
    if not callable(getter):
        return frame
    schema_names = list(getter().column_names)
    if not schema_names:
        return frame

    columns = list(frame.columns)
    rename = {
        columns[i]: schema_names[i]
        for i in range(min(len(columns), len(schema_names)))
        if columns[i] != schema_names[i]
    }
    if rename:
        frame = frame.rename(rename)

    for name in schema_names[len(columns) :]:
        frame = frame.with_columns(pl.lit(None).cast(pl.Utf8).alias(name))

    if len(columns) > len(schema_names):
        return frame.select(schema_names)

    return frame


def _project_columns(
    frame: pl.DataFrame,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
) -> pl.DataFrame:
    wanted = list(dict.fromkeys([*identity_columns, *compare_columns]))
    existing = [name for name in wanted if name in frame.columns]
    if not existing:
        return frame
    return frame.select(existing)


def _flat_parse_to_polars(
    source: BytesIO | Any,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
) -> pl.DataFrame:
    payload = source.read()
    text = payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else payload
    if skip_rows:
        lines = text.splitlines()
        text = "\n".join(lines[skip_rows:])
    parsed = parse_lines(
        split_physical_lines(text),
        delimiter,
        has_header=has_header,
    )
    if not parsed.rows:
        return pl.DataFrame()
    columns = parsed.headers or [f"col_{i}" for i in range(len(parsed.rows[0]))]
    column_data: dict[str, list[str | None]] = {name: [] for name in columns}
    for row in parsed.rows:
        for idx, name in enumerate(columns):
            column_data[name].append(row[idx] if idx < len(row) else None)
    return pl.DataFrame(column_data)


def _load_delimited_frame(
    adapter: FileDelimitedAdapter,
    *,
    identity_columns: list[str] | None = None,
    compare_columns: list[str] | None = None,
) -> pl.DataFrame:
    column_names = _headerless_column_names(adapter)
    if pyarrow_supports_delimiter(adapter._delimiter):
        frame = table_to_polars(
            read_csv_table(
                adapter.path,
                delimiter=adapter._delimiter,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
                column_names=column_names,
            )
        )
        frame = _align_frame_to_schema(frame, adapter)
    else:
        with open(adapter.path, "rb") as handle:
            frame = _flat_parse_to_polars(
                handle,
                delimiter=adapter._delimiter,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
            )
        frame = _align_frame_to_schema(frame, adapter)
    if identity_columns is not None and compare_columns is not None:
        return _project_columns(frame, identity_columns=identity_columns, compare_columns=compare_columns)
    return frame


def _load_gcs_delimited_frame(
    adapter: object,
    *,
    identity_columns: list[str] | None = None,
    compare_columns: list[str] | None = None,
) -> pl.DataFrame:
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
    from pegasus.validation.gcs_object import open_gcs_binary

    if not isinstance(adapter, GcsDelimitedAdapter):
        raise TypeError("expected GcsDelimitedAdapter")

    column_names = _headerless_column_names(adapter)
    size = adapter.get_size_bytes()
    adapter.ensure_object_cached()
    cached = adapter.cached_object_bytes()
    if cached is not None and len(cached) >= size:
        payload = cached[:size]
        if pyarrow_supports_delimiter(adapter._delimiter):
            frame = table_to_polars(
                read_csv_bytes(
                    payload,
                    delimiter=adapter._delimiter,
                    has_header=adapter._has_header,
                    skip_rows=adapter._skip_rows,
                    column_names=column_names,
                )
            )
            frame = _align_frame_to_schema(frame, adapter)
        else:
            frame = _flat_parse_to_polars(
                BytesIO(payload),
                delimiter=adapter._delimiter,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
            )
            frame = _align_frame_to_schema(frame, adapter)
        if identity_columns is not None and compare_columns is not None:
            return _project_columns(frame, identity_columns=identity_columns, compare_columns=compare_columns)
        return frame

    with open_gcs_binary(adapter._ref) as handle:
        if pyarrow_supports_delimiter(adapter._delimiter):
            frame = table_to_polars(
                read_csv_binary(
                    handle,
                    delimiter=adapter._delimiter,
                    has_header=adapter._has_header,
                    skip_rows=adapter._skip_rows,
                    column_names=column_names,
                )
            )
            frame = _align_frame_to_schema(frame, adapter)
        else:
            frame = _flat_parse_to_polars(
                handle,
                delimiter=adapter._delimiter,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
            )
            frame = _align_frame_to_schema(frame, adapter)
    if identity_columns is not None and compare_columns is not None:
        return _project_columns(frame, identity_columns=identity_columns, compare_columns=compare_columns)
    return frame


def _load_frame(
    adapter: TabularSourceAdapter,
    *,
    identity_columns: list[str] | None = None,
    compare_columns: list[str] | None = None,
) -> pl.DataFrame | None:
    if isinstance(adapter, FileDelimitedAdapter):
        return _load_delimited_frame(
            adapter,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
        )

    adapter_type = type(adapter).__name__
    if adapter_type == "GcsDelimitedAdapter":
        return _load_gcs_delimited_frame(
            adapter,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
        )

    path = Path(adapter.path)
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
    if not _should_use_in_memory(source, target, memory_budget_bytes=memory_budget_bytes):
        return None

    t0 = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            src_fut = pool.submit(
                _load_frame,
                source,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
            )
            tgt_fut = pool.submit(
                _load_frame,
                target,
                identity_columns=identity_columns,
                compare_columns=compare_columns,
            )
            src = src_fut.result()
            tgt = tgt_fut.result()
        if src is None or tgt is None:
            return None

        src = src.with_columns(_fingerprint_expr(compare_columns).alias("_fp"))
        tgt = tgt.with_columns(_fingerprint_expr(compare_columns).alias("_fp"))

        src_id_fp = src.select([*identity_columns, "_fp"])
        tgt_id_fp = tgt.select([*identity_columns, "_fp"])

        missing_df = src_id_fp.join(
            tgt_id_fp.select(identity_columns),
            on=identity_columns,
            how="anti",
        )
        extra_df = tgt_id_fp.join(
            src_id_fp.select(identity_columns),
            on=identity_columns,
            how="anti",
        )

        inner = src_id_fp.join(
            tgt_id_fp,
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
            if mtype == "changed" and with_cols:
                keys = frame.select(identity_columns).head(take)
                detail = keys.join(
                    src.select([*identity_columns, *compare_columns]),
                    on=identity_columns,
                    how="left",
                ).join(
                    tgt.select([*identity_columns, *compare_columns]),
                    on=identity_columns,
                    how="left",
                    suffix="_tgt",
                )
                for row in detail.iter_rows(named=True):
                    key = _identity_key_from_row(row, identity_columns)
                    col_diffs: list[ColumnDifference] = []
                    for col in compare_columns:
                        sv = _canonical(row.get(col))
                        tv = _canonical(row.get(f"{col}_tgt"))
                        if sv != tv:
                            col_diffs.append(ColumnDifference(col, sv, tv))
                    samples.append(MismatchSample(key, mtype, col_diffs))
            else:
                for row in frame.head(take).iter_rows(named=True):
                    samples.append(MismatchSample(_identity_key_from_row(row, identity_columns), mtype))

        _append_samples(missing_df, "missing")
        _append_samples(extra_df, "extra")
        _append_samples(changed_df, "changed", with_cols=enable_column_drilldown)

        elapsed = time.perf_counter() - t0
        return PipelineResult(
            schema_valid=True,
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
    except Exception:
        return None
