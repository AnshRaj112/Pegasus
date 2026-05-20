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
from pegasus.validation.compare_rules import CompareRule
from pegasus.validation.value_compare import polars_values_differ_expr

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
    omit_row_detail
        When ``True``, :meth:`compare_dataframes` defaults to emitting placeholder
        ``row_detail`` (unless overridden per call). Intended for partitioned / huge runs.

    Notes
    -----
    Duplicate UID values within either frame are rejected before comparison. Normalize
    upstream or aggregate first.
    """

    __slots__ = ("_stringify_null_in_report", "_omit_row_detail")

    def __init__(self, *, stringify_null_in_report: bool = False, omit_row_detail: bool = False) -> None:
        self._stringify_null_in_report = stringify_null_in_report
        self._omit_row_detail = omit_row_detail

    def compare_dataframes(
        self,
        source: pl.DataFrame,
        target: pl.DataFrame,
        *,
        uid_column: str,
        compare_columns: Sequence[str] | None = None,
        omit_row_detail: bool | None = None,
        compare_rules: dict[str, CompareRule] | None = None,
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
        omit_row_detail
            When ``True``, ``row_detail`` is a tiny placeholder instead of full JSON row
            snapshots. Use for huge partitioned runs to avoid multi‑GB RAM from millions
            of mismatch rows (UI still has uid / column / cell values). When ``None``,
            uses the value from the constructor's ``omit_row_detail``.

        Returns
        -------
        MismatchReport
            ``mismatches`` table columns: ``uid``, ``mismatch_type``, ``column_name``,
            ``source_value``, ``target_value``, ``row_detail``.

        Raises
        ------
        UIDComparisonError
            Missing UID column, no overlapping compare columns, or duplicate UIDs.
        """
        omit = self._omit_row_detail if omit_row_detail is None else omit_row_detail
        self._validate_frames(source, target, uid_column)
        compare_cols = self._resolve_compare_columns(source, target, uid_column, compare_columns)

        logger.info(
            "Starting UID comparison uid_column=%r compare_columns=%d source_rows=%d target_rows=%d omit_row_detail=%s",
            uid_column,
            len(compare_cols),
            source.height,
            target.height,
            omit,
        )

        src_uid = source.select(pl.col(uid_column).alias("_pegasus_uid"))
        tgt_uid = target.select(pl.col(uid_column).alias("_pegasus_uid"))

        missing_parts = self._missing_in_target(source, uid_column, tgt_uid, omit_row_detail=omit)
        extra_parts = self._extra_in_target(target, uid_column, src_uid, omit_row_detail=omit)
        value_parts = self._value_mismatches(
            source,
            target,
            uid_column,
            compare_cols,
            omit_row_detail=omit,
            compare_rules=compare_rules,
        )

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
        *,
        omit_row_detail: bool,
    ) -> pl.DataFrame:
        missing_rows = source.join(tgt_uid, left_on=uid_column, right_on="_pegasus_uid", how="anti")
        if missing_rows.is_empty():
            return empty_mismatch_frame()

        if omit_row_detail:
            return missing_rows.select(
                pl.col(uid_column).cast(pl.String).alias("uid"),
                pl.lit(MismatchType.MISSING_IN_TARGET.value).cast(pl.String).alias("mismatch_type"),
                pl.lit(None, dtype=pl.String).alias("column_name"),
                pl.lit(None, dtype=pl.String).alias("source_value"),
                pl.lit(None, dtype=pl.String).alias("target_value"),
                pl.lit("{}").alias("row_detail"),
            )

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
        *,
        omit_row_detail: bool,
    ) -> pl.DataFrame:
        extra_rows = target.join(src_uid, left_on=uid_column, right_on="_pegasus_uid", how="anti")
        if extra_rows.is_empty():
            return empty_mismatch_frame()

        if omit_row_detail:
            return extra_rows.select(
                pl.col(uid_column).cast(pl.String).alias("uid"),
                pl.lit(MismatchType.EXTRA_IN_TARGET.value).cast(pl.String).alias("mismatch_type"),
                pl.lit(None, dtype=pl.String).alias("column_name"),
                pl.lit(None, dtype=pl.String).alias("source_value"),
                pl.lit(None, dtype=pl.String).alias("target_value"),
                pl.lit("{}").alias("row_detail"),
            )

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
        *,
        omit_row_detail: bool,
        compare_rules: dict[str, CompareRule] | None = None,
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

        # Join source and target with suffix for comparison
        joined = src_m.join(tgt_m, on=uid_column, how="inner", suffix="_target")

        # Build horizontal any-diff filter to skip fully-matching rows
        rules = compare_rules or {}
        diff_exprs = [
            polars_values_differ_expr(name, f"{name}_target", rules.get(name))
            for name in compare_columns
        ]
        any_diff = pl.any_horizontal(diff_exprs)
        mismatched = joined.filter(any_diff)

        if mismatched.is_empty():
            return empty_mismatch_frame()

        # For each column, extract mismatched rows — cheap in-memory filters (no re-join)
        mismatch_chunks: list[pl.DataFrame] = []
        _COLUMN_CHUNK = 64

        for chunk_start in range(0, len(compare_columns), _COLUMN_CHUNK):
            chunk_cols = list(compare_columns[chunk_start : chunk_start + _COLUMN_CHUNK])
            for name in chunk_cols:
                tgt_col = f"{name}_target"
                if tgt_col not in mismatched.columns:
                    continue

                mask = polars_values_differ_expr(name, tgt_col, rules.get(name))
                diff = mismatched.filter(mask)
                if diff.is_empty():
                    continue

                logger.debug("Value mismatches on column %r count=%d", name, diff.height)

                # Vectorized null handling for source/target values
                if self._stringify_null_in_report:
                    sv = pl.col(name).cast(pl.String).fill_null("<null>").alias("source_value")
                    tv = pl.col(tgt_col).cast(pl.String).fill_null("<null>").alias("target_value")
                else:
                    sv = pl.col(name).cast(pl.String).alias("source_value")
                    tv = pl.col(tgt_col).cast(pl.String).alias("target_value")

                chunk_df = diff.select([
                    pl.col(uid_column).cast(pl.String).alias("uid"),
                    pl.lit(MismatchType.VALUE_MISMATCH.value).alias("mismatch_type"),
                    pl.lit(name).alias("column_name"),
                    sv,
                    tv,
                    pl.lit("{}").alias("row_detail"),
                ])

                # If row_detail is needed, build it vectorized via struct JSON encoding
                if not omit_row_detail:
                    src_cols = [pl.col(c).alias(c) for c in compare_columns if c in diff.columns]
                    tgt_aliases = [
                        pl.col(f"{c}_target").alias(c)
                        for c in compare_columns
                        if f"{c}_target" in diff.columns
                    ]
                    if src_cols and tgt_aliases:
                        src_json = diff.select(
                            pl.col(uid_column),
                            pl.struct([pl.col(uid_column)] + src_cols).struct.json_encode().alias("_src_json"),
                        )
                        tgt_json = diff.select(
                            pl.col(uid_column),
                            pl.struct([pl.col(uid_column)] + tgt_aliases).struct.json_encode().alias("_tgt_json"),
                        )
                        detail_df = src_json.join(tgt_json, on=uid_column).select(
                            pl.col(uid_column),
                            pl.concat_str([
                                pl.lit('{"source_record":'),
                                pl.col("_src_json"),
                                pl.lit(',"target_record":'),
                                pl.col("_tgt_json"),
                                pl.lit("}"),
                            ]).alias("row_detail"),
                        )
                        chunk_df = chunk_df.drop("row_detail").join(
                            detail_df.select(
                                pl.col(uid_column).cast(pl.String).alias("uid"),
                                pl.col("row_detail"),
                            ),
                            on="uid",
                            how="left",
                        )

                mismatch_chunks.append(chunk_df)

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
