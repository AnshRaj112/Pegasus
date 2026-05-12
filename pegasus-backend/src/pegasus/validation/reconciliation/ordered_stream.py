"""Ordered two-sided UID reconciliation for globally sorted row streams."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import polars as pl
import polars.exceptions as pl_exc

from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader

from .exceptions import ReconciliationError
from .metrics import NoOpReconciliationMetrics, ReconciliationMetrics
from .mismatch_collector import MismatchSink, compare_aligned_row_dicts

logger = logging.getLogger(__name__)


class _RowCursor:
    """Sequential row iterator over Polars ``collect_batches`` streams."""

    __slots__ = ("_uid_column", "_it", "_batch", "_idx", "_rows_dicts")

    def __init__(self, batch_iter: Iterator[pl.DataFrame], *, uid_column: str) -> None:
        self._uid_column = uid_column
        self._it = batch_iter
        self._batch: pl.DataFrame | None = None
        self._idx = 0
        self._rows_dicts: list[dict[str, Any]] | None = None

    def _load_next_batch(self) -> bool:
        try:
            self._batch = next(self._it)
        except StopIteration:
            self._batch = None
            self._rows_dicts = None
            self._idx = 0
            return False
        self._rows_dicts = self._batch.to_dicts()
        self._idx = 0
        return True

    def _ensure(self) -> bool:
        if self._batch is None and self._rows_dicts is None:
            return self._load_next_batch()
        if self._rows_dicts is not None and self._idx >= len(self._rows_dicts):
            return self._load_next_batch()
        return self._batch is not None and self._rows_dicts is not None

    def peek(self) -> dict[str, Any] | None:
        if not self._ensure():
            return None
        assert self._rows_dicts is not None
        return self._rows_dicts[self._idx]

    def pop(self) -> dict[str, Any] | None:
        row = self.peek()
        if row is None:
            return None
        self._idx += 1
        return row


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
) -> tuple[int, int]:
    """Two-pointer merge for **globally sorted** UTF-8 CSV inputs (``window=0`` semantics)."""
    m = metrics or NoOpReconciliationMetrics()
    read_opts: dict[str, object] = {
        "separator": delimiter,
        "encoding": "utf-8",
        "has_header": True,
    }

    def _batches(path: Path) -> Iterator[pl.DataFrame]:
        return iter(reader.iter_batches(path, batch_size=batch_rows, read_options=read_opts))

    src_cursor = _RowCursor(_batches(source_path), uid_column=uid_column)
    tgt_cursor = _RowCursor(_batches(target_path), uid_column=uid_column)

    src_rows = 0
    tgt_rows = 0
    m.on_phase_start("ordered_stream_merge", source=str(source_path), target=str(target_path))
    try:
        while True:
            s_row = src_cursor.peek()
            t_row = tgt_cursor.peek()
            if s_row is None and t_row is None:
                break
            if s_row is None:
                assert t_row is not None
                tgt_rows += 1
                uid = str(t_row[uid_column])
                collector.add_extra(uid=uid, target_record=t_row)
                tgt_cursor.pop()
                continue
            if t_row is None:
                src_rows += 1
                uid = str(s_row[uid_column])
                collector.add_missing(uid=uid, source_record=s_row)
                src_cursor.pop()
                continue

            s_uid = str(s_row[uid_column])
            t_uid = str(t_row[uid_column])
            if s_uid == t_uid:
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
                src_cursor.pop()
                tgt_cursor.pop()
            elif s_uid < t_uid:
                src_rows += 1
                collector.add_missing(uid=s_uid, source_record=s_row)
                src_cursor.pop()
            else:
                tgt_rows += 1
                collector.add_extra(uid=t_uid, target_record=t_row)
                tgt_cursor.pop()
    except pl_exc.PolarsError as exc:
        logger.exception("Ordered stream merge failed")
        raise ReconciliationError("Ordered stream merge failed while reading CSV batches") from exc

    m.on_phase_end("ordered_stream_merge", source_rows=src_rows, target_rows=tgt_rows)
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
) -> tuple[int, int]:
    m = metrics or NoOpReconciliationMetrics()
    src_it = pl.scan_parquet(source_path).collect_batches(chunk_size=batch_rows, engine="streaming")
    tgt_it = pl.scan_parquet(target_path).collect_batches(chunk_size=batch_rows, engine="streaming")
    src_cursor = _RowCursor(src_it, uid_column=uid_column)
    tgt_cursor = _RowCursor(tgt_it, uid_column=uid_column)

    src_rows = 0
    tgt_rows = 0
    m.on_phase_start("ordered_parquet_merge", source=str(source_path), target=str(target_path))
    try:
        while True:
            s_row = src_cursor.peek()
            t_row = tgt_cursor.peek()
            if s_row is None and t_row is None:
                break
            if s_row is None:
                assert t_row is not None
                tgt_rows += 1
                collector.add_extra(uid=str(t_row[uid_column]), target_record=t_row)
                tgt_cursor.pop()
                continue
            if t_row is None:
                src_rows += 1
                collector.add_missing(uid=str(s_row[uid_column]), source_record=s_row)
                src_cursor.pop()
                continue

            s_uid = str(s_row[uid_column])
            t_uid = str(t_row[uid_column])
            if s_uid == t_uid:
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
                src_cursor.pop()
                tgt_cursor.pop()
            elif s_uid < t_uid:
                src_rows += 1
                collector.add_missing(uid=s_uid, source_record=s_row)
                src_cursor.pop()
            else:
                tgt_rows += 1
                collector.add_extra(uid=t_uid, target_record=t_row)
                tgt_cursor.pop()
    except pl_exc.PolarsError as exc:
        logger.exception("Ordered parquet merge failed")
        raise ReconciliationError("Ordered parquet merge failed while scanning sorted outputs") from exc

    m.on_phase_end("ordered_parquet_merge", source_rows=src_rows, target_rows=tgt_rows)
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
    src_cursor = _RowCursor(src_it, uid_column=uid_column)
    tgt_cursor = _RowCursor(tgt_it, uid_column=uid_column)

    src_buf: deque[dict[str, Any]] = deque()
    tgt_buf: deque[dict[str, Any]] = deque()

    def _fill_side(buf: deque[dict[str, Any]], cur: _RowCursor, *, max_total: int) -> None:
        while len(buf) < max_total:
            row = cur.peek()
            if row is None:
                return
            buf.append(row)
            cur.pop()

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
