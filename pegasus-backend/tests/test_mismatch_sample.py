"""Tests for stratified mismatch sampling."""

from __future__ import annotations

import polars as pl
import pytest

from pegasus.api.v1.mismatch_sample import (
    allocate_category_sample_limits,
    build_stratified_mismatch_sample,
    value_mismatch_counts_by_column,
)
from pegasus.validation.comparators.models import MismatchType


def _row(
    uid: str,
    mismatch_type: str,
    *,
    column: str | None = None,
) -> dict:
    return {
        "uid": uid,
        "mismatch_type": mismatch_type,
        "column_name": column,
        "source_value": "s",
        "target_value": "t",
        "row_detail": "{}",
    }


def test_stratified_sample_includes_multiple_value_columns() -> None:
    """head(n) would be all 'amount' first; stratified mixes columns."""
    rows: list[dict] = []
    for i in range(120):
        rows.append(_row(f"u{i}", MismatchType.VALUE_MISMATCH, column="amount"))
    for j in range(15):
        rows.append(_row(f"v{j}", MismatchType.VALUE_MISMATCH, column="region"))

    df = pl.DataFrame(rows)
    out = build_stratified_mismatch_sample(df, 40)

    assert out.height == 40
    cols = out["column_name"].to_list()
    assert "amount" in cols
    assert "region" in cols


@pytest.mark.parametrize("limit", [0, -1])
def test_non_positive_limit_returns_empty(limit: int) -> None:
    df = pl.DataFrame([_row("a", MismatchType.VALUE_MISMATCH, column="x")])
    out = build_stratified_mismatch_sample(df, limit)
    assert out.height == 0


def test_non_value_mismatches_are_front_loaded() -> None:
    rows = (
        [_row("m1", MismatchType.MISSING_IN_TARGET, column=None)] * 5
        + [_row("e1", MismatchType.EXTRA_IN_TARGET, column=None)] * 3
        + [_row(f"a{i}", MismatchType.VALUE_MISMATCH, column="amount") for i in range(50)]
        + [_row(f"r{i}", MismatchType.VALUE_MISMATCH, column="region") for i in range(50)]
    )
    df = pl.DataFrame(rows)
    out = build_stratified_mismatch_sample(df, 20)

    types = out["mismatch_type"].to_list()
    assert types[:8].count(MismatchType.MISSING_IN_TARGET) == 5
    assert types[:8].count(MismatchType.EXTRA_IN_TARGET) == 3
    assert MismatchType.VALUE_MISMATCH in types


def test_allocate_reserves_at_least_one_row_per_nonempty_category_when_budget_allows() -> None:
    """Regression: old divmod+slack could assign the entire budget to value_mismatch only."""
    m, e, v = allocate_category_sample_limits(40, 40, 42, 100)
    assert m >= 1 and e >= 1 and v >= 1
    assert m + e + v == 100


def test_value_mismatch_counts_by_column() -> None:
    rows = [
        _row("1", MismatchType.VALUE_MISMATCH, column="amount"),
        _row("2", MismatchType.VALUE_MISMATCH, column="amount"),
        _row("3", MismatchType.VALUE_MISMATCH, column="region"),
        _row("4", MismatchType.MISSING_IN_TARGET, column=None),
    ]
    df = pl.DataFrame(rows)
    counts = value_mismatch_counts_by_column(df)
    assert counts == {"amount": 2, "region": 1}
