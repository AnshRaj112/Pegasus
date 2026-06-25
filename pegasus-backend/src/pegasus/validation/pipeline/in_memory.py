# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T11:33:45Z
# --- END GENERATED FILE METADATA ---

"""In-memory reconciliation for datasets that fit in RAM (fast path)."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import Any

import polars as pl

from pegasus.validation.adapters.base import TabularSourceAdapter
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.comparators.models import MismatchType, empty_mismatch_frame

_HEADERLESS_ADAPTER_TYPES = frozenset({"FileDelimitedAdapter", "GcsDelimitedAdapter"})
from pegasus.validation.readers.clevercsv_io import clevercsv_to_polars, flat_file_to_polars
from pegasus.validation.pipeline.fingerprint import canonical, filter_compare_columns
from pegasus.validation.pipeline.result import ColumnDifference, MismatchSample, PipelineResult
from pegasus.validation.pipeline.row_sanity import assert_reasonable_row_counts
from pegasus.validation.pipeline.timing import PipelineIoStats, PipelineTimings, attach_stage_report
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

logger = logging.getLogger(__name__)


def _identity_key_from_row(row: dict[str, Any], columns: list[str]) -> str:
    return "|".join(canonical(row.get(c)) for c in columns)


def _serialize_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _record_payload(record_key: str, row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    record: dict[str, Any] = {"uid": record_key}
    for col in columns:
        if col in row:
            record[col] = _serialize_cell(row.get(col))
    return record


def _row_detail_json(
    *,
    source_record: dict[str, Any] | None = None,
    target_record: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {}
    if source_record:
        payload["source_record"] = source_record
    if target_record:
        payload["target_record"] = target_record
    return json.dumps(payload, ensure_ascii=False) if payload else ""


def _column_diffs_for_row(
    row: dict[str, Any],
    *,
    record_key: str,
    compare_columns: list[str],
    src_physical: list[str],
    tgt_physical: list[str],
    pol: Any,
) -> list[ColumnDifference]:
    col_diffs: list[ColumnDifference] = []
    src_row = {k: row.get(k) for k in src_physical}
    tgt_row = {k: row.get(f"{k}_tgt", row.get(k)) for k in tgt_physical}
    for col in compare_columns:
        if pol is not None and pol.fields:
            if not pol.values_equal_mapped(col, src_row, tgt_row):
                sv = pol.canonical_side_part(src_row, col, side="source")
                tv = pol.canonical_side_part(tgt_row, col, side="target")
                col_diffs.append(ColumnDifference(col, sv, tv))
        else:
            sv = canonical(row.get(col), column=col)
            tv = canonical(row.get(f"{col}_tgt"), column=col)
            if sv != tv:
                col_diffs.append(ColumnDifference(col, sv, tv))
    return col_diffs


def build_in_memory_mismatch_frame(
    *,
    missing_df: pl.DataFrame,
    extra_df: pl.DataFrame,
    changed_df: pl.DataFrame,
    src: pl.DataFrame,
    tgt: pl.DataFrame,
    identity_columns: list[str],
    compare_columns: list[str],
    src_physical: list[str],
    tgt_physical: list[str],
    enable_column_drilldown: bool,
    pol: Any,
) -> pl.DataFrame:
    """Materialize every mismatch row for NDJSON export / persistence."""
    rows: list[dict[str, Any]] = []
    src_lookup = src.select(list(dict.fromkeys([*identity_columns, *compare_columns])))
    tgt_lookup = tgt.select(list(dict.fromkeys([*identity_columns, *compare_columns])))

    if missing_df.height > 0:
        for row in missing_df.join(src_lookup, on=identity_columns, how="left").iter_rows(named=True):
            key = _identity_key_from_row(row, identity_columns)
            source_record = _record_payload(key, row, compare_columns)
            rows.append({
                "uid": key,
                "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                "column_name": None,
                "source_value": None,
                "target_value": None,
                "row_detail": _row_detail_json(source_record=source_record, target_record=None),
            })

    if extra_df.height > 0:
        for row in extra_df.join(tgt_lookup, on=identity_columns, how="left").iter_rows(named=True):
            key = _identity_key_from_row(row, identity_columns)
            target_record = _record_payload(key, row, compare_columns)
            rows.append({
                "uid": key,
                "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                "column_name": None,
                "source_value": None,
                "target_value": None,
                "row_detail": _row_detail_json(source_record=None, target_record=target_record),
            })

    if changed_df.height > 0 and enable_column_drilldown:
        src_cols = list(dict.fromkeys([*identity_columns, *src_physical]))
        tgt_cols = list(dict.fromkeys([*identity_columns, *tgt_physical]))
        detail = (
            changed_df.select(identity_columns)
            .join(src.select([c for c in src_cols if c in src.columns]), on=identity_columns, how="left")
            .join(
                tgt.select([c for c in tgt_cols if c in tgt.columns]),
                on=identity_columns,
                how="left",
                suffix="_tgt",
            )
        )
        for row in detail.iter_rows(named=True):
            key = _identity_key_from_row(row, identity_columns)
            col_diffs = _column_diffs_for_row(
                row,
                record_key=key,
                compare_columns=compare_columns,
                src_physical=src_physical,
                tgt_physical=tgt_physical,
                pol=pol,
            )
            if not col_diffs:
                continue
            source_record = _record_payload(key, row, compare_columns)
            target_record = {
                "uid": key,
                **{
                    col: _serialize_cell(row.get(f"{col}_tgt", row.get(col)))
                    for col in compare_columns
                    if f"{col}_tgt" in row or col in row
                },
            }
            row_detail = _row_detail_json(source_record=source_record, target_record=target_record)
            for cd in col_diffs:
                sv = _serialize_cell(cd.source_value)
                tv = _serialize_cell(cd.target_value)
                if pol is not None:
                    sv = pol.mask_if_sensitive(cd.column, sv)
                    tv = pol.mask_if_sensitive(cd.column, tv)
                rows.append({
                    "uid": key,
                    "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                    "column_name": cd.column,
                    "source_value": sv,
                    "target_value": tv,
                    "row_detail": row_detail,
                })

    return pl.DataFrame(rows) if rows else empty_mismatch_frame()


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
    auto_in_memory_max_bytes: int = _DEFAULT_AUTO_IN_MEMORY_MAX_BYTES,
    max_file_bytes: int = 512 * 1024 * 1024,
) -> bool:
    source_bytes = _adapter_size_bytes(source)
    target_bytes = _adapter_size_bytes(target)
    if source_bytes is None or target_bytes is None:
        return False
    file_bytes = source_bytes + target_bytes
    if file_bytes <= auto_in_memory_max_bytes:
        return True
    if file_bytes > max_file_bytes:
        return False
    return file_bytes * 4 < int(memory_budget_bytes * 0.65)


def should_try_in_memory_reconcile(
    *,
    enable_in_memory_reconcile: bool,
    auto_in_memory_max_bytes: int,
    source_bytes: int,
    target_bytes: int,
    memory_budget_bytes: int | None = None,
) -> bool:
    """Return whether combined inputs are small enough for the Polars in-memory fast path."""
    if not enable_in_memory_reconcile:
        return source_bytes + target_bytes <= auto_in_memory_max_bytes
    combined = source_bytes + target_bytes
    cap = max(auto_in_memory_max_bytes, _DEFAULT_AUTO_IN_MEMORY_MAX_BYTES)
    if memory_budget_bytes is not None and memory_budget_bytes > 0:
        cap = min(cap, int(memory_budget_bytes * 0.40))
    return combined <= cap


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
    physical_columns: list[str] | None = None,
) -> pl.DataFrame:
    wanted = list(dict.fromkeys([*identity_columns, *(physical_columns or compare_columns)]))
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
    if hasattr(source, "seek"):
        source.seek(0)
    frame = clevercsv_to_polars(
        source,
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=skip_rows,
    )
    if frame is not None:
        return frame
    if hasattr(source, "seek"):
        source.seek(0)
    path = getattr(source, "name", None)
    return flat_file_to_polars(
        source,
        delimiter=delimiter,
        has_header=has_header,
        skip_rows=skip_rows,
        path=Path(path) if path else None,
    )


def _load_delimited_frame(
    adapter: FileDelimitedAdapter,
    *,
    identity_columns: list[str] | None = None,
    compare_columns: list[str] | None = None,
    physical_columns: list[str] | None = None,
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
        from pegasus.validation.readers.multichar_csv import can_use_fast_multichar_load, load_multichar_csv_fast

        if can_use_fast_multichar_load(adapter.path, adapter._delimiter):
            frame = load_multichar_csv_fast(
                adapter.path,
                delimiter=adapter._delimiter,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
            )
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
        return _project_columns(
            frame,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
            physical_columns=physical_columns,
        )
    return frame


def _load_gcs_delimited_frame(
    adapter: object,
    *,
    identity_columns: list[str] | None = None,
    compare_columns: list[str] | None = None,
    physical_columns: list[str] | None = None,
) -> pl.DataFrame:
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter

    if not isinstance(adapter, GcsDelimitedAdapter):
        raise TypeError("expected GcsDelimitedAdapter")

    from pegasus.validation.gcs_stream import get_gcs_stream_session

    from io import BytesIO

    from pegasus.validation.readers.multichar_csv import (
        can_use_fast_multichar_load_bytes,
        load_multichar_csv_fast,
    )

    column_names = _headerless_column_names(adapter)
    adapter.warm_metadata()
    session = get_gcs_stream_session(adapter._ref)
    with session.open_binary() as handle:
        data = handle.read()
    session.store_cached_object_body(data)
    stream = BytesIO(data)
    if pyarrow_supports_delimiter(adapter._delimiter):
        frame = table_to_polars(
            read_csv_binary(
                stream,
                delimiter=adapter._delimiter,
                has_header=adapter._has_header,
                skip_rows=adapter._skip_rows,
                column_names=column_names,
            )
        )
        frame = _align_frame_to_schema(frame, adapter)
    elif can_use_fast_multichar_load_bytes(data, adapter._delimiter):
        frame = load_multichar_csv_fast(
            stream,
            delimiter=adapter._delimiter,
            has_header=adapter._has_header,
            skip_rows=adapter._skip_rows,
        )
        frame = _align_frame_to_schema(frame, adapter)
    else:
        stream.seek(0)
        frame = _flat_parse_to_polars(
            stream,
            delimiter=adapter._delimiter,
            has_header=adapter._has_header,
            skip_rows=adapter._skip_rows,
        )
        frame = _align_frame_to_schema(frame, adapter)
    adapter._network_transfer_seconds = max(
        adapter._network_transfer_seconds,
        session.network_transfer_seconds,
    )
    if identity_columns is not None and compare_columns is not None:
        return _project_columns(
            frame,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
            physical_columns=physical_columns,
        )
    return frame


def _load_frame(
    adapter: TabularSourceAdapter,
    *,
    identity_columns: list[str] | None = None,
    compare_columns: list[str] | None = None,
    physical_columns: list[str] | None = None,
) -> pl.DataFrame | None:
    if isinstance(adapter, FileDelimitedAdapter):
        return _load_delimited_frame(
            adapter,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
            physical_columns=physical_columns,
        )

    adapter_type = type(adapter).__name__
    if adapter_type == "GcsDelimitedAdapter":
        return _load_gcs_delimited_frame(
            adapter,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
            physical_columns=physical_columns,
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


def _fingerprint_expr(columns: list[str], *, side: str = "source") -> pl.Expr:
    from pegasus.validation.pipeline.polars_spill import _mapping_fingerprint_expr

    return _mapping_fingerprint_expr(columns, side=side).alias("_fp")


def try_in_memory_reconcile(
    source: TabularSourceAdapter,
    target: TabularSourceAdapter,
    *,
    identity_columns: list[str],
    compare_columns: list[str],
    memory_budget_bytes: int,
    enable_column_drilldown: bool,
    auto_in_memory_max_bytes: int = _DEFAULT_AUTO_IN_MEMORY_MAX_BYTES,
    sample_limit: int = 1000,
) -> PipelineResult | None:
    """Return a :class:`PipelineResult` when both sides fit in memory; else ``None``."""
    if not _should_use_in_memory(
        source,
        target,
        memory_budget_bytes=memory_budget_bytes,
        auto_in_memory_max_bytes=auto_in_memory_max_bytes,
    ):
        return None

    from pegasus.validation.comparators.policy import active_compare_policy

    pol = active_compare_policy()
    logical_keys = pol.compare_keys if pol and pol.fields else compare_columns
    src_physical = pol.physical_columns("source") if pol and pol.fields else compare_columns
    tgt_physical = pol.physical_columns("target") if pol and pol.fields else compare_columns

    t0 = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            src_fut = pool.submit(
                _load_frame,
                source,
                identity_columns=identity_columns,
                compare_columns=logical_keys,
                physical_columns=src_physical,
            )
            tgt_fut = pool.submit(
                _load_frame,
                target,
                identity_columns=identity_columns,
                compare_columns=logical_keys,
                physical_columns=tgt_physical,
            )
            src = src_fut.result()
            tgt = tgt_fut.result()
        if src is None or tgt is None:
            return None

        compare_columns = logical_keys
        if not compare_columns:
            logger.warning("in_memory reconcile: no compare columns in loaded frame")
            return None

        assert_reasonable_row_counts(
            source,
            target,
            source_rows=src.height,
            target_rows=tgt.height,
            compare_column_count=len(compare_columns),
        )

        src = src.with_columns(_fingerprint_expr(compare_columns, side="source"))
        tgt = tgt.with_columns(_fingerprint_expr(compare_columns, side="target"))

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

        from pegasus.api.v1.mismatch_sample import allocate_category_sample_limits

        samples: list[MismatchSample] = []
        miss_cap, ext_cap, val_cap = allocate_category_sample_limits(
            missing_df.height,
            extra_df.height,
            changed_df.height,
            sample_limit,
        )

        def _append_samples(
            frame: pl.DataFrame,
            mtype: str,
            *,
            with_cols: bool = False,
            max_take: int = 0,
        ) -> None:
            if max_take <= 0 or frame.is_empty():
                return
            take = min(max_take, frame.height)
            if mtype == "changed" and with_cols:
                keys = frame.select(identity_columns).head(take)
                src_cols = list(dict.fromkeys([*identity_columns, *src_physical]))
                tgt_cols = list(dict.fromkeys([*identity_columns, *tgt_physical]))
                detail = keys.join(
                    src.select([c for c in src_cols if c in src.columns]),
                    on=identity_columns,
                    how="left",
                ).join(
                    tgt.select([c for c in tgt_cols if c in tgt.columns]),
                    on=identity_columns,
                    how="left",
                    suffix="_tgt",
                )
                for row in detail.iter_rows(named=True):
                    key = _identity_key_from_row(row, identity_columns)
                    col_diffs = _column_diffs_for_row(
                        row,
                        record_key=key,
                        compare_columns=compare_columns,
                        src_physical=src_physical,
                        tgt_physical=tgt_physical,
                        pol=pol,
                    )
                    samples.append(MismatchSample(key, mtype, col_diffs))
            else:
                for row in frame.head(take).iter_rows(named=True):
                    samples.append(MismatchSample(_identity_key_from_row(row, identity_columns), mtype))

        _append_samples(missing_df, "missing", max_take=miss_cap)
        _append_samples(extra_df, "extra", max_take=ext_cap)
        _append_samples(
            changed_df,
            "changed",
            with_cols=enable_column_drilldown,
            max_take=val_cap,
        )

        full_mismatches = build_in_memory_mismatch_frame(
            missing_df=missing_df,
            extra_df=extra_df,
            changed_df=changed_df,
            src=src,
            tgt=tgt,
            identity_columns=identity_columns,
            compare_columns=compare_columns,
            src_physical=src_physical,
            tgt_physical=tgt_physical,
            enable_column_drilldown=enable_column_drilldown,
            pol=pol,
        )

        elapsed = time.perf_counter() - t0
        extra_stats: dict[str, Any] = {"path": "in_memory_polars"}
        timings = PipelineTimings(total_seconds=elapsed, total_cpu_seconds=elapsed)
        io = PipelineIoStats(
            source_input_bytes=_adapter_size_bytes(source) or 0,
            target_input_bytes=_adapter_size_bytes(target) or 0,
        )
        attach_stage_report(extra_stats, timings, io)
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
            full_mismatches=full_mismatches,
            compared_columns=list(compare_columns),
            execution_seconds=elapsed,
            extra_stats=extra_stats,
        )
    except Exception as exc:
        logger.warning(
            "in_memory reconcile failed (%s); falling back to spill",
            exc,
            exc_info=True,
        )
        return None
