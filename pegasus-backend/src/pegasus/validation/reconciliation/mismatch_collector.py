"""Accumulate mismatch rows in bounded chunks (Polars frames), then build a :class:`MismatchReport`."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, TextIO

import polars as pl

from pegasus.validation.comparators.models import (
    MISMATCH_REPORT_SCHEMA,
    MismatchReport,
    MismatchType,
    empty_mismatch_frame,
)

from .row_detail import encode_row_detail

logger = logging.getLogger(__name__)


class MismatchSink(Protocol):
    """Minimal interface for streaming / in-memory mismatch sinks used by merge logic."""

    def add_missing(self, *, uid: str, source_record: dict[str, Any]) -> None: ...

    def add_extra(self, *, uid: str, target_record: dict[str, Any]) -> None: ...

    def add_value_mismatch(
        self,
        *,
        uid: str,
        column_name: str,
        source_value: Any,
        target_value: Any,
        source_record: dict[str, Any],
        target_record: dict[str, Any],
        row_detail: str | None = None,
    ) -> None: ...

    def extend_from_mismatches_frame(self, frame: pl.DataFrame) -> None: ...

    def finish(self) -> MismatchReport: ...


class MismatchCollector:
    """Collect long-form mismatch rows without holding one giant Python list.

    Internally stores a list of small :class:`polars.DataFrame` chunks (default 8k rows)
    and concatenates once at :meth:`finish`.
    """

    def __init__(
        self,
        *,
        chunk_cap: int = 8192,
        stringify_null_in_report: bool = True,
        omit_row_detail: bool = False,
        ndjson_mirror_path: Path | None = None,
    ) -> None:
        if chunk_cap < 256:
            raise ValueError("chunk_cap must be >= 256")
        self._chunks: list[pl.DataFrame] = []
        self._chunk_cap = chunk_cap
        self._stringify_null = stringify_null_in_report
        self._omit_row_detail = omit_row_detail
        self._ndjson_mirror_path = ndjson_mirror_path
        self._ndjson_fp: TextIO | None = None
        self._incremental_summary: dict[str, int] = defaultdict(int)
        self._buf_missing: list[dict[str, Any]] = []
        self._buf_extra: list[dict[str, Any]] = []
        self._buf_value: list[dict[str, Any]] = []

    @property
    def omit_row_detail(self) -> bool:
        """When True, ``row_detail`` is ``\"{}\"`` instead of full JSON (partitioned / huge runs)."""
        return self._omit_row_detail

    def _maybe_flush(self) -> None:
        total = len(self._buf_missing) + len(self._buf_extra) + len(self._buf_value)
        if total < self._chunk_cap:
            return
        # Flush largest buffer first to keep memory predictable.
        if len(self._buf_value) >= len(self._buf_missing) and len(self._buf_value) >= len(self._buf_extra):
            self._flush_value_buffer()
        elif len(self._buf_missing) >= len(self._buf_extra):
            self._flush_missing_buffer()
        else:
            self._flush_extra_buffer()

    def _flush_missing_buffer(self) -> None:
        if not self._buf_missing:
            return
        records = self._buf_missing
        self._buf_missing = []
        if self._omit_row_detail:
            rows = [
                {
                    "uid": r["uid"],
                    "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": "{}",
                }
                for r in records
            ]
        else:
            rows = [
                {
                    "uid": r["uid"],
                    "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": encode_row_detail(r["source_record"], None),
                }
                for r in records
            ]
        self._chunks.append(pl.DataFrame(rows, schema=_SCHEMA))
        self._incremental_summary[MismatchType.MISSING_IN_TARGET.value] += len(rows)
        self._mirror_ndjson_rows(rows)

    def _flush_extra_buffer(self) -> None:
        if not self._buf_extra:
            return
        records = self._buf_extra
        self._buf_extra = []
        if self._omit_row_detail:
            rows = [
                {
                    "uid": r["uid"],
                    "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": "{}",
                }
                for r in records
            ]
        else:
            rows = [
                {
                    "uid": r["uid"],
                    "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": encode_row_detail(None, r["target_record"]),
                }
                for r in records
            ]
        self._chunks.append(pl.DataFrame(rows, schema=_SCHEMA))
        self._incremental_summary[MismatchType.EXTRA_IN_TARGET.value] += len(rows)
        self._mirror_ndjson_rows(rows)

    def _flush_value_buffer(self) -> None:
        if not self._buf_value:
            return
        records = self._buf_value
        self._buf_value = []
        rows = [
            {
                "uid": r["uid"],
                "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                "column_name": r["column_name"],
                "source_value": r["source_value"],
                "target_value": r["target_value"],
                "row_detail": r["row_detail"],
            }
            for r in records
        ]
        self._chunks.append(pl.DataFrame(rows, schema=_SCHEMA))
        self._incremental_summary[MismatchType.VALUE_MISMATCH.value] += len(rows)
        self._mirror_ndjson_rows(rows)

    def _mirror_ndjson_rows(self, rows: list[dict[str, Any]]) -> None:
        if self._ndjson_mirror_path is None or not rows:
            return
        if self._ndjson_fp is None:
            self._ndjson_mirror_path.parent.mkdir(parents=True, exist_ok=True)
            self._ndjson_fp = self._ndjson_mirror_path.open("w", encoding="utf-8")
        for r in rows:
            self._ndjson_fp.write(json.dumps(r, default=str, ensure_ascii=False))
            self._ndjson_fp.write("\n")

    def add_missing(self, *, uid: str, source_record: dict[str, Any]) -> None:
        """Record a row present only on the source side."""
        self._buf_missing.append({"uid": uid, "source_record": source_record})
        self._maybe_flush()

    def add_extra(self, *, uid: str, target_record: dict[str, Any]) -> None:
        """Record a row present only on the target side."""
        self._buf_extra.append({"uid": uid, "target_record": target_record})
        self._maybe_flush()

    def add_value_mismatch(
        self,
        *,
        uid: str,
        column_name: str,
        source_value: Any,
        target_value: Any,
        source_record: dict[str, Any],
        target_record: dict[str, Any],
        row_detail: str | None = None,
    ) -> None:
        """Record a column-level difference for a shared UID."""
        sv = self._serialize_cell(source_value)
        tv = self._serialize_cell(target_value)
        if row_detail is not None:
            detail = row_detail
        else:
            detail = "{}" if self._omit_row_detail else encode_row_detail(source_record, target_record)
        self._buf_value.append(
            {
                "uid": uid,
                "column_name": column_name,
                "source_value": sv,
                "target_value": tv,
                "row_detail": detail,
            }
        )
        self._maybe_flush()

    def _serialize_cell(self, value: Any) -> str | None:
        if value is None and not self._stringify_null:
            return None
        if self._stringify_null and value is None:
            return "<null>"
        return str(value)

    def extend_from_mismatches_frame(self, frame: pl.DataFrame) -> None:
        """Append an already-canonical mismatch table (for example per-partition results)."""
        if frame.is_empty():
            return
        self._chunks.append(
            frame.select(
                [
                    pl.col("uid").cast(pl.String),
                    pl.col("mismatch_type").cast(pl.String),
                    pl.col("column_name").cast(pl.String),
                    pl.col("source_value").cast(pl.String),
                    pl.col("target_value").cast(pl.String),
                    pl.col("row_detail").cast(pl.String),
                ]
            )
        )
        counts = frame.group_by("mismatch_type").len()
        for row in counts.iter_rows(named=True):
            self._incremental_summary[str(row["mismatch_type"])] += int(row["len"])
        mirror_rows = frame.to_dicts()
        self._mirror_ndjson_rows(mirror_rows)

    def finish(self) -> MismatchReport:
        """Concatenate buffers into the canonical :class:`MismatchReport` schema."""
        self._flush_missing_buffer()
        self._flush_extra_buffer()
        self._flush_value_buffer()
        if self._ndjson_fp is not None:
            self._ndjson_fp.close()
            self._ndjson_fp = None
            logger.info("Mismatch NDJSON mirror closed path=%s", self._ndjson_mirror_path)

        if not self._chunks:
            mismatches = empty_mismatch_frame()
            summary = {
                MismatchType.MISSING_IN_TARGET.value: 0,
                MismatchType.EXTRA_IN_TARGET.value: 0,
                MismatchType.VALUE_MISMATCH.value: 0,
            }
            return MismatchReport(mismatches=mismatches, summary=summary)

        mismatches = pl.concat(self._chunks, how="vertical_relaxed").select(
            [
                pl.col("uid").cast(pl.String),
                pl.col("mismatch_type").cast(pl.String),
                pl.col("column_name").cast(pl.String),
                pl.col("source_value").cast(pl.String),
                pl.col("target_value").cast(pl.String),
                pl.col("row_detail").cast(pl.String),
            ]
        )
        if self._incremental_summary:
            summary = {
                k: int(self._incremental_summary.get(k, 0))
                for k in (
                    MismatchType.MISSING_IN_TARGET.value,
                    MismatchType.EXTRA_IN_TARGET.value,
                    MismatchType.VALUE_MISMATCH.value,
                )
            }
        else:
            summary_series = mismatches.group_by("mismatch_type").len().sort("mismatch_type")
            summary = {row["mismatch_type"]: row["len"] for row in summary_series.iter_rows(named=True)}
        for key in (
            MismatchType.MISSING_IN_TARGET.value,
            MismatchType.EXTRA_IN_TARGET.value,
            MismatchType.VALUE_MISMATCH.value,
        ):
            summary.setdefault(key, 0)

        logger.info(
            "MismatchCollector finished missing=%s extra=%s value=%s total_rows=%d",
            summary.get(MismatchType.MISSING_IN_TARGET.value, 0),
            summary.get(MismatchType.EXTRA_IN_TARGET.value, 0),
            summary.get(MismatchType.VALUE_MISMATCH.value, 0),
            mismatches.height,
        )
        return MismatchReport(mismatches=mismatches, summary=summary)


_SCHEMA: dict[str, pl.DataType] = dict(MISMATCH_REPORT_SCHEMA)


def compare_aligned_row_dicts(
    *,
    uid: str,
    uid_column: str,
    compare_columns: Sequence[str],
    source_row: dict[str, Any],
    target_row: dict[str, Any],
    collector: MismatchSink,
    compare_rules: dict[str, Any] | None = None,
) -> None:
    """Field-compare two aligned rows (same UID) and push any differences to *collector*."""
    for name in compare_columns:
        s_val = source_row.get(name)
        t_val = target_row.get(name)
        rule = (compare_rules or {}).get(name)
        if _eq_missing(s_val, t_val, rule):
            continue
        collector.add_value_mismatch(
            uid=uid,
            column_name=name,
            source_value=s_val,
            target_value=t_val,
            source_record=source_row,
            target_record=target_row,
        )


def _eq_missing(left: Any, right: Any, rule: Any = None) -> bool:
    """Return True when two aligned cell values are equal (including cross-format dates)."""
    from pegasus.validation.value_compare import values_equal_for_validation

    return values_equal_for_validation(left, right, rule)
