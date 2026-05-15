"""Ordered two-sided UID reconciliation for globally sorted row streams."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import polars as pl
import polars.exceptions as pl_exc

from more_itertools import peekable

from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader

from .exceptions import ReconciliationError
from .metrics import NoOpReconciliationMetrics, ReconciliationMetrics
from .mismatch_collector import MismatchSink, compare_aligned_row_dicts
from .vectorized_compare import emit_value_mismatches_single_pass

logger = logging.getLogger(__name__)


def _is_internal_join_col(name: str) -> bool:
    return name == "pegasus_part" or name.startswith("pegasus_")


def _joined_presence_row_detail_exprs(
    joined_cols: Sequence[str],
    *,
    omit_row_detail: bool,
) -> tuple[pl.Expr, pl.Expr]:
    """Build ``row_detail`` JSON for missing (source row) and extra (target row) from an outer-join schema."""
    empty = pl.lit("{}", dtype=pl.String)
    if omit_row_detail:
        return empty, empty
    src_cols = [c for c in joined_cols if not c.endswith("_target") and not _is_internal_join_col(c)]
    tgt_aliases = [
        pl.col(c).alias(c[: -len("_target")])
        for c in joined_cols
        if c.endswith("_target") and not _is_internal_join_col(c[: -len("_target")])
    ]
    miss_inner = pl.struct([pl.col(c) for c in src_cols]).struct.json_encode()
    missing_rd = pl.concat_str(
        [pl.lit('{"source_record":'), miss_inner, pl.lit(',"target_record":null}')]
    )
    ext_inner = (
        pl.struct(tgt_aliases).struct.json_encode()
        if tgt_aliases
        else pl.lit("null", dtype=pl.String)
    )
    extra_rd = pl.concat_str(
        [pl.lit('{"source_record":null,"target_record":'), ext_inner, pl.lit("}")]
    )
    return missing_rd, extra_rd


def _batch_to_dict_iter(batch_iter: Iterator[pl.DataFrame]) -> Iterator[dict[str, Any]]:
    for batch in batch_iter:
        yield from batch.to_dicts()


def merge_sorted_csv_streams(
    *,
    source_path: Path,
    target_path: Path,
    uid_column: str,
    compare_columns: list[str],
    delimiter: str,
    reader: PolarsCSVReader,
    collector: MismatchSink,
    batch_rows: int,
    metrics: ReconciliationMetrics | None = None,
    omit_row_detail: bool = False,
) -> tuple[int, int]:
    """Two-pointer merge for **globally sorted** UTF-8 CSV inputs (``window=0`` semantics)."""
    m = metrics or NoOpReconciliationMetrics()
    m.on_phase_start("vectorized_csv_merge", source=str(source_path), target=str(target_path))
    
    # Use Polars to read both sorted CSVs and join them
    read_opts: dict[str, object] = {
        "separator": delimiter,
        "has_header": True,
        "encoding": "utf8-lossy",
    }
    
    src_lf = pl.scan_csv(str(source_path), **read_opts)
    tgt_lf = pl.scan_csv(str(target_path), **read_opts)
    
    # Join
    joined = src_lf.join(tgt_lf, on=uid_column, how="outer", suffix="_target")
    jcols = joined.collect_schema().names()
    miss_rd, ext_rd = _joined_presence_row_detail_exprs(jcols, omit_row_detail=omit_row_detail)

    # 1. Missing
    missing = joined.filter(pl.col(f"{uid_column}_target").is_null()).select([
        pl.col(uid_column).cast(pl.String).alias("uid"),
        pl.lit("missing_in_target").alias("mismatch_type"),
        pl.lit(None, dtype=pl.String).alias("column_name"),
        pl.lit(None, dtype=pl.String).alias("source_value"),
        pl.lit(None, dtype=pl.String).alias("target_value"),
        miss_rd.alias("row_detail"),
    ])

    # 2. Extra
    extra = joined.filter(pl.col(uid_column).is_null()).select([
        pl.col(f"{uid_column}_target").cast(pl.String).alias("uid"),
        pl.lit("extra_in_target").alias("mismatch_type"),
        pl.lit(None, dtype=pl.String).alias("column_name"),
        pl.lit(None, dtype=pl.String).alias("source_value"),
        pl.lit(None, dtype=pl.String).alias("target_value"),
        ext_rd.alias("row_detail"),
    ])
    
    # 3. Value Mismatch — single-pass vectorized
    both = joined.filter(pl.col(uid_column).is_not_null() & pl.col(f"{uid_column}_target").is_not_null())

    src_rows = src_lf.select(pl.len()).collect().item()
    tgt_rows = tgt_lf.select(pl.len()).collect().item()

    # Emit missing/extra
    if hasattr(collector, "bulk_append_from_frame"):
        collector.bulk_append_from_frame(missing.collect(engine="streaming"))
        collector.bulk_append_from_frame(extra.collect(engine="streaming"))
    else:
        for rec in missing.collect(engine="streaming").to_dicts():
            collector.add_missing(uid=str(rec["uid"]), source_record=rec)
        for rec in extra.collect(engine="streaming").to_dicts():
            collector.add_extra(uid=str(rec["uid"]), target_record=rec)

    # Single-pass value mismatch detection (replaces per-column loop)
    emit_value_mismatches_single_pass(
        both,
        uid_column=uid_column,
        compare_columns=compare_columns,
        collector=collector,
    )

    m.on_phase_end("vectorized_csv_merge", source_rows=src_rows, target_rows=tgt_rows)
    return src_rows, tgt_rows


def merge_sorted_parquet_streams(
    *,
    source_path: Path,
    target_path: Path,
    uid_column: str,
    compare_columns: list[str],
    collector: MismatchSink,
    batch_rows: int,
    window: int,
    metrics: ReconciliationMetrics | None = None,
    omit_row_detail: bool = False,
) -> tuple[int, int]:
    """Merge-join two **globally sorted** Parquet files produced by external sort.

    When ``window > 0``, apply bounded look-ahead on both sides (mostly-sorted mode).
    """
    if window <= 0:
        return _merge_parquet_two_pointer(
            source_path=source_path,
            target_path=target_path,
            uid_column=uid_column,
            compare_columns=compare_columns,
            collector=collector,
            batch_rows=batch_rows,
            metrics=metrics,
            omit_row_detail=omit_row_detail,
        )
    return _merge_parquet_sliding(
        source_path=source_path,
        target_path=target_path,
        uid_column=uid_column,
        compare_columns=compare_columns,
        collector=collector,
        batch_rows=batch_rows,
        window=window,
        metrics=metrics,
    )


def _merge_parquet_two_pointer(
    *,
    source_path: Path,
    target_path: Path,
    uid_column: str,
    compare_columns: list[str],
    collector: MismatchSink,
    batch_rows: int,
    metrics: ReconciliationMetrics | None,
    omit_row_detail: bool = False,
) -> tuple[int, int]:
    m = metrics or NoOpReconciliationMetrics()
    m.on_phase_start("vectorized_parquet_merge", source=str(source_path), target=str(target_path))
    
    src_lf = pl.scan_parquet(source_path)
    tgt_lf = pl.scan_parquet(target_path)
    
    # Outer join to find all differences
    joined = src_lf.join(tgt_lf, on=uid_column, how="outer", suffix="_target")
    jcols = joined.collect_schema().names()
    miss_rd, ext_rd = _joined_presence_row_detail_exprs(jcols, omit_row_detail=omit_row_detail)

    # 1. Missing in Target (Missing)
    missing = joined.filter(pl.col(f"{uid_column}_target").is_null()).select([
        pl.col(uid_column).cast(pl.String).alias("uid"),
        pl.lit("missing_in_target").alias("mismatch_type"),
        pl.lit(None, dtype=pl.String).alias("column_name"),
        pl.lit(None, dtype=pl.String).alias("source_value"),
        pl.lit(None, dtype=pl.String).alias("target_value"),
        miss_rd.alias("row_detail"),
    ])

    # 2. Extra in Target (Extra)
    extra = joined.filter(pl.col(uid_column).is_null()).select([
        pl.col(f"{uid_column}_target").cast(pl.String).alias("uid"),
        pl.lit("extra_in_target").alias("mismatch_type"),
        pl.lit(None, dtype=pl.String).alias("column_name"),
        pl.lit(None, dtype=pl.String).alias("source_value"),
        pl.lit(None, dtype=pl.String).alias("target_value"),
        ext_rd.alias("row_detail"),
    ])
    
    # 3. Value Mismatch — single-pass vectorized
    both = joined.filter(pl.col(uid_column).is_not_null() & pl.col(f"{uid_column}_target").is_not_null())

    src_rows = src_lf.select(pl.len()).collect().item()
    tgt_rows = tgt_lf.select(pl.len()).collect().item()

    # Emit missing/extra
    if hasattr(collector, "bulk_append_from_frame"):
        collector.bulk_append_from_frame(missing.collect(engine="streaming"))
        collector.bulk_append_from_frame(extra.collect(engine="streaming"))
    else:
        for rec in missing.collect(engine="streaming").to_dicts():
            collector.add_missing(uid=str(rec["uid"]), source_record=rec)
        for rec in extra.collect(engine="streaming").to_dicts():
            collector.add_extra(uid=str(rec["uid"]), target_record=rec)

    # Single-pass value mismatch detection (replaces per-column loop)
    emit_value_mismatches_single_pass(
        both,
        uid_column=uid_column,
        compare_columns=compare_columns,
        collector=collector,
    )

    m.on_phase_end("vectorized_parquet_merge", source_rows=src_rows, target_rows=tgt_rows)
    return src_rows, tgt_rows


def _merge_parquet_sliding(
    *,
    source_path: Path,
    target_path: Path,
    uid_column: str,
    compare_columns: list[str],
    collector: MismatchSink,
    batch_rows: int,
    window: int,
    metrics: ReconciliationMetrics | None,
) -> tuple[int, int]:
    """Bounded look-ahead on whichever side lags lexicographically by UID."""
    m = metrics or NoOpReconciliationMetrics()
    src_it = pl.scan_parquet(source_path).collect_batches(chunk_size=batch_rows, engine="streaming")
    tgt_it = pl.scan_parquet(target_path).collect_batches(chunk_size=batch_rows, engine="streaming")
    src_cursor = peekable(_batch_to_dict_iter(src_it))
    tgt_cursor = peekable(_batch_to_dict_iter(tgt_it))

    src_buf: deque[dict[str, Any]] = deque()
    tgt_buf: deque[dict[str, Any]] = deque()

    def _fill_side(buf: deque[dict[str, Any]], cur: peekable, *, max_total: int) -> None:
        while len(buf) < max_total:
            row = cur.peek(None)
            if row is None:
                return
            buf.append(row)
            next(cur)

    src_rows = tgt_rows = 0
    m.on_phase_start("sliding_window_parquet_merge", window=window)

    try:
        while True:
            _fill_side(src_buf, src_cursor, max_total=max(1, window))
            _fill_side(tgt_buf, tgt_cursor, max_total=max(1, window))
            if not src_buf and not tgt_buf:
                break

            if not src_buf:
                row = tgt_buf.popleft()
                tgt_rows += 1
                collector.add_extra(uid=str(row[uid_column]), target_record=row)
                continue
            if not tgt_buf:
                row = src_buf.popleft()
                src_rows += 1
                collector.add_missing(uid=str(row[uid_column]), source_record=row)
                continue

            s_uid = str(src_buf[0][uid_column])
            t_uid = str(tgt_buf[0][uid_column])
            if s_uid == t_uid:
                s_row = src_buf.popleft()
                t_row = tgt_buf.popleft()
                src_rows += 1
                tgt_rows += 1
                compare_aligned_row_dicts(
                    uid=s_uid,
                    uid_column=uid_column,
                    compare_columns=compare_columns,
                    source_row=s_row,
                    target_row=t_row,
                    collector=collector,
                )
                continue

            if s_uid < t_uid:
                # Try to find s_uid within the next (window-1) target rows already buffered or load more.
                found_idx = -1
                for i in range(min(len(tgt_buf), window)):
                    if str(tgt_buf[i][uid_column]) == s_uid:
                        found_idx = i
                        break
                if found_idx == -1 and len(tgt_buf) < window:
                    _fill_side(tgt_buf, tgt_cursor, max_total=window)
                    for i in range(len(tgt_buf)):
                        if str(tgt_buf[i][uid_column]) == s_uid:
                            found_idx = i
                            break

                if found_idx == -1:
                    row = src_buf.popleft()
                    src_rows += 1
                    collector.add_missing(uid=str(row[uid_column]), source_record=row)
                    continue

                for _ in range(found_idx):
                    tr = tgt_buf.popleft()
                    tgt_rows += 1
                    collector.add_extra(uid=str(tr[uid_column]), target_record=tr)
                continue

            # s_uid > t_uid — symmetric
            found_idx = -1
            for i in range(min(len(src_buf), window)):
                if str(src_buf[i][uid_column]) == t_uid:
                    found_idx = i
                    break
            if found_idx == -1 and len(src_buf) < window:
                _fill_side(src_buf, src_cursor, max_total=window)
                for i in range(len(src_buf)):
                    if str(src_buf[i][uid_column]) == t_uid:
                        found_idx = i
                        break

            if found_idx == -1:
                tr = tgt_buf.popleft()
                tgt_rows += 1
                collector.add_extra(uid=str(tr[uid_column]), target_record=tr)
                continue

            for _ in range(found_idx):
                sr = src_buf.popleft()
                src_rows += 1
                collector.add_missing(uid=str(sr[uid_column]), source_record=sr)
    except pl_exc.PolarsError as exc:
        logger.exception("Sliding-window parquet merge failed")
        raise ReconciliationError("Sliding-window parquet merge failed") from exc

    m.on_phase_end("sliding_window_parquet_merge", source_rows=src_rows, target_rows=tgt_rows)
    return src_rows, tgt_rows
