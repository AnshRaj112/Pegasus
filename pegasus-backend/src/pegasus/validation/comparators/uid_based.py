"""UID-keyed comparison of source and target Polars frames."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl
import polars.exceptions as pl_exc

from pegasus.validation.comparators.base import ValidationComparator
from pegasus.validation.comparators.exceptions import ComparisonError, UIDComparisonError
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame

logger = logging.getLogger(__name__)


def _encode_row_detail(
    source_record: dict[str, Any] | None,
    target_record: dict[str, Any] | None,
) -> str:
    """JSON payload for UIs: full source/target rows when available."""
    return json.dumps(
        {"source_record": source_record, "target_record": target_record},
        default=str,
        ensure_ascii=False,
    )


class UIDBasedComparator:
    """Compare *source* (expected) and *target* (actual) :class:`polars.DataFrame` rows by UID.

    Uses anti-joins and selective semi-joins so only UID lists and matched subsets are
    combined—full copies of both frames are avoided beyond what Polars requires for the
    joins you request.

    Parameters
    ----------
    stringify_null_in_report
        When ``True``, null-like cells appear as the literal ``\"<null>\"`` in the
        report strings instead of Polars/JSON null (easier for logs and CSV exports).

    Notes
    -----
    Duplicate UID values within either frame are rejected before comparison. Normalize
    upstream or aggregate first.
    """

    __slots__ = ("_stringify_null_in_report",)

    def __init__(self, *, stringify_null_in_report: bool = False) -> None:
        self._stringify_null_in_report = stringify_null_in_report

    def compare_dataframes(
        self,
        source: pl.DataFrame,
        target: pl.DataFrame,
        *,
        uid_column: str,
        compare_columns: Sequence[str] | None = None,
    ) -> MismatchReport:
        """Match rows on ``uid_column`` and emit a long-form :class:`MismatchReport`.

        Parameters
        ----------
        source
            Reference dataset (e.g. golden / expected).
        target
            Dataset under test (e.g. ingest output).
        uid_column
            Column name present in both frames; values compared as strings for joining.
        compare_columns
            Columns to diff on intersecting rows. Defaults to all shared columns except
            ``uid_column``.

        Returns
        -------
        MismatchReport
            ``mismatches`` table columns: ``uid``, ``mismatch_type``, ``column_name``,
            ``source_value``, ``target_value``. Row-level issues use null ``column_name``
            and null detail columns unless row snapshots are enabled later.

        Raises
        ------
        UIDComparisonError
            Missing UID column, no overlapping compare columns, or duplicate UIDs.
        """
        self._validate_frames(source, target, uid_column)
        compare_cols = self._resolve_compare_columns(source, target, uid_column, compare_columns)

        logger.info(
            "Starting UID comparison uid_column=%r compare_columns=%d source_rows=%d target_rows=%d",
            uid_column,
            len(compare_cols),
            source.height,
            target.height,
        )

        src_uid = source.select(pl.col(uid_column).alias("_pegasus_uid"))
        tgt_uid = target.select(pl.col(uid_column).alias("_pegasus_uid"))

        missing_parts = self._missing_in_target(source, uid_column, tgt_uid)
        extra_parts = self._extra_in_target(target, uid_column, src_uid)
        value_parts = self._value_mismatches(source, target, uid_column, compare_cols)

        frames = [f for f in (missing_parts, extra_parts, value_parts) if f.height > 0]
        if not frames:
            mismatches = empty_mismatch_frame()
            summary = {
                MismatchType.MISSING_IN_TARGET.value: 0,
                MismatchType.EXTRA_IN_TARGET.value: 0,
                MismatchType.VALUE_MISMATCH.value: 0,
            }
            logger.info("UID comparison complete: no mismatches")
            return MismatchReport(mismatches=mismatches, summary=summary)

        mismatches = pl.concat(frames, how="vertical_relaxed").select(
            [
                pl.col("uid").cast(pl.String),
                pl.col("mismatch_type").cast(pl.String),
                pl.col("column_name").cast(pl.String),
                pl.col("source_value").cast(pl.String),
                pl.col("target_value").cast(pl.String),
                pl.col("row_detail").cast(pl.String),
            ]
        )
        summary_series = mismatches.group_by("mismatch_type").len().sort("mismatch_type")
        summary = {row["mismatch_type"]: row["len"] for row in summary_series.iter_rows(named=True)}
        for key in (
            MismatchType.MISSING_IN_TARGET.value,
            MismatchType.EXTRA_IN_TARGET.value,
            MismatchType.VALUE_MISMATCH.value,
        ):
            summary.setdefault(key, 0)

        logger.info(
            "UID comparison complete missing=%s extra=%s value=%s total_report_rows=%d",
            summary.get(MismatchType.MISSING_IN_TARGET.value, 0),
            summary.get(MismatchType.EXTRA_IN_TARGET.value, 0),
            summary.get(MismatchType.VALUE_MISMATCH.value, 0),
            mismatches.height,
        )
        return MismatchReport(mismatches=mismatches, summary=summary)

    def _validate_frames(
        self,
        source: pl.DataFrame,
        target: pl.DataFrame,
        uid_column: str,
    ) -> None:
        if uid_column not in source.columns:
            raise UIDComparisonError(f"uid_column {uid_column!r} not in source columns")
        if uid_column not in target.columns:
            raise UIDComparisonError(f"uid_column {uid_column!r} not in target columns")

        src_dup = (
            source.group_by(uid_column)
            .len()
            .filter(pl.col("len") > 1)
            .height
        )
        if src_dup:
            logger.error("Source frame has duplicate UID values for column %r", uid_column)
            raise UIDComparisonError(f"Duplicate uid values in source column {uid_column!r}")

        tgt_dup = (
            target.group_by(uid_column)
            .len()
            .filter(pl.col("len") > 1)
            .height
        )
        if tgt_dup:
            logger.error("Target frame has duplicate UID values for column %r", uid_column)
            raise UIDComparisonError(f"Duplicate uid values in target column {uid_column!r}")

    def _resolve_compare_columns(
        self,
        source: pl.DataFrame,
        target: pl.DataFrame,
        uid_column: str,
        compare_columns: Sequence[str] | None,
    ) -> list[str]:
        if compare_columns is None:
            src_set = set(source.columns)
            tgt_set = set(target.columns)
            compare_cols = sorted((src_set & tgt_set) - {uid_column})
        else:
            compare_cols = list(dict.fromkeys(compare_columns))
            unknown_s = [c for c in compare_cols if c not in source.columns]
            unknown_t = [c for c in compare_cols if c not in target.columns]
            if unknown_s or unknown_t:
                raise UIDComparisonError(
                    f"compare_columns missing from source={unknown_s} target={unknown_t}"
                )

        if not compare_cols:
            logger.warning("No overlapping columns to compare besides uid_column=%r", uid_column)

        return compare_cols

    def _missing_in_target(
        self,
        source: pl.DataFrame,
        uid_column: str,
        tgt_uid: pl.DataFrame,
    ) -> pl.DataFrame:
        missing_rows = source.join(tgt_uid, left_on=uid_column, right_on="_pegasus_uid", how="anti")
        if missing_rows.is_empty():
            return empty_mismatch_frame()

        records = missing_rows.to_dicts()
        details = [_encode_row_detail(dict(r), None) for r in records]
        return pl.DataFrame(
            {
                "uid": [str(r[uid_column]) for r in records],
                "mismatch_type": [MismatchType.MISSING_IN_TARGET.value] * len(records),
                "column_name": [None] * len(records),
                "source_value": [None] * len(records),
                "target_value": [None] * len(records),
                "row_detail": details,
            },
            schema={
                "uid": pl.String,
                "mismatch_type": pl.String,
                "column_name": pl.String,
                "source_value": pl.String,
                "target_value": pl.String,
                "row_detail": pl.String,
            },
        )

    def _extra_in_target(
        self,
        target: pl.DataFrame,
        uid_column: str,
        src_uid: pl.DataFrame,
    ) -> pl.DataFrame:
        extra_rows = target.join(src_uid, left_on=uid_column, right_on="_pegasus_uid", how="anti")
        if extra_rows.is_empty():
            return empty_mismatch_frame()

        records = extra_rows.to_dicts()
        details = [_encode_row_detail(None, dict(r)) for r in records]
        return pl.DataFrame(
            {
                "uid": [str(r[uid_column]) for r in records],
                "mismatch_type": [MismatchType.EXTRA_IN_TARGET.value] * len(records),
                "column_name": [None] * len(records),
                "source_value": [None] * len(records),
                "target_value": [None] * len(records),
                "row_detail": details,
            },
            schema={
                "uid": pl.String,
                "mismatch_type": pl.String,
                "column_name": pl.String,
                "source_value": pl.String,
                "target_value": pl.String,
                "row_detail": pl.String,
            },
        )

    def _value_mismatches(
        self,
        source: pl.DataFrame,
        target: pl.DataFrame,
        uid_column: str,
        compare_columns: Sequence[str],
    ) -> pl.DataFrame:
        if not compare_columns:
            return empty_mismatch_frame()

        src_keys = source.select([uid_column]).join(
            target.select([uid_column]),
            on=uid_column,
            how="inner",
        )
        if src_keys.is_empty():
            return empty_mismatch_frame()

        src_m = source.join(src_keys, on=uid_column, how="inner").unique(subset=[uid_column])
        tgt_m = target.join(src_keys, on=uid_column, how="inner").unique(subset=[uid_column])

        prefixed = [pl.col(uid_column)]
        right_exprs: list[pl.Expr] = []
        for name in compare_columns:
            prefixed.append(pl.col(name).alias(f"__src__{name}"))
            right_exprs.append(pl.col(name).alias(f"__tgt__{name}"))

        joined = src_m.select(prefixed).join(
            tgt_m.select([pl.col(uid_column)] + right_exprs),
            on=uid_column,
            how="inner",
        )

        mismatch_chunks: list[pl.DataFrame] = []
        for name in compare_columns:
            left_c = f"__src__{name}"
            right_c = f"__tgt__{name}"
            diff = joined.filter(~pl.col(left_c).eq_missing(pl.col(right_c)))
            if diff.is_empty():
                continue
            logger.debug("Value mismatches on column %r count=%d", name, diff.height)
            uids: list[str] = []
            src_cells: list[str | None] = []
            tgt_cells: list[str | None] = []
            details: list[str] = []
            for row in diff.iter_rows(named=True):
                uids.append(str(row[uid_column]))
                src_cells.append(
                    None
                    if row[left_c] is None and not self._stringify_null_in_report
                    else (
                        "<null>"
                        if self._stringify_null_in_report and row[left_c] is None
                        else str(row[left_c])
                    )
                )
                tgt_cells.append(
                    None
                    if row[right_c] is None and not self._stringify_null_in_report
                    else (
                        "<null>"
                        if self._stringify_null_in_report and row[right_c] is None
                        else str(row[right_c])
                    )
                )
                rec_src = {uid_column: row[uid_column]}
                rec_tgt = {uid_column: row[uid_column]}
                for cn in compare_columns:
                    rec_src[cn] = row[f"__src__{cn}"]
                    rec_tgt[cn] = row[f"__tgt__{cn}"]
                details.append(_encode_row_detail(rec_src, rec_tgt))

            mismatch_chunks.append(
                pl.DataFrame(
                    {
                        "uid": uids,
                        "mismatch_type": [MismatchType.VALUE_MISMATCH.value] * len(uids),
                        "column_name": [name] * len(uids),
                        "source_value": src_cells,
                        "target_value": tgt_cells,
                        "row_detail": details,
                    },
                    schema={
                        "uid": pl.String,
                        "mismatch_type": pl.String,
                        "column_name": pl.String,
                        "source_value": pl.String,
                        "target_value": pl.String,
                        "row_detail": pl.String,
                    },
                )
            )

        if not mismatch_chunks:
            return empty_mismatch_frame()

        return pl.concat(mismatch_chunks, how="vertical_relaxed")


class UIDKeyedLazyComparator(ValidationComparator):
    """:class:`ValidationComparator` that materializes lazy inputs and runs :class:`UIDBasedComparator`.

    .. warning::

        Both ``expected`` and ``actual`` are fully collected in memory. Prefer
        :class:`UIDBasedComparator` on pre-materialized chunks when datasets are huge.
    """

    __slots__ = ("_inner",)

    def __init__(
        self,
        *,
        inner: UIDBasedComparator | None = None,
        stringify_null_in_report: bool = False,
    ) -> None:
        self._inner = inner or UIDBasedComparator(stringify_null_in_report=stringify_null_in_report)

    def compare(
        self,
        expected: pl.LazyFrame,
        actual: pl.LazyFrame,
        *,
        key_columns: Sequence[str],
        compare_columns: Sequence[str] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> pl.LazyFrame:
        """Join on the single UID in ``key_columns`` and return mismatch rows as a lazy frame."""
        _ = context
        if len(key_columns) != 1:
            raise ComparisonError(
                "UIDKeyedLazyComparator expects exactly one entry in key_columns (the uid column name)"
            )
        uid_column = key_columns[0]
        logger.info("Collecting lazy frames for UIDKeyedLazyComparator uid_column=%r", uid_column)
        try:
            src = expected.collect()
            tgt = actual.collect()
        except pl_exc.PolarsError as exc:
            logger.exception("Failed to collect lazy frames for UID comparison")
            raise ComparisonError("Polars failed while collecting frames for comparison") from exc

        report = self._inner.compare_dataframes(
            src,
            tgt,
            uid_column=uid_column,
            compare_columns=compare_columns,
        )
        return report.mismatches.lazy()
