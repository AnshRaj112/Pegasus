"""Tests for :class:`UIDBasedComparator` and :class:`UIDKeyedLazyComparator`."""

from __future__ import annotations

import json

import polars as pl
import pytest

from pegasus.validation.comparators import (
    ComparisonError,
    MismatchType,
    UIDBasedComparator,
    UIDComparisonError,
    UIDKeyedLazyComparator,
)


def test_missing_extra_and_value_mismatch():
    source = pl.DataFrame(
        {
            "uid": ["a", "b", "c"],
            "x": [1, 2, 3],
            "y": ["p", "q", "r"],
        }
    )
    target = pl.DataFrame(
        {
            "uid": ["a", "b", "d"],
            "x": [1, 9, 4],
            "y": ["p", "q", "s"],
        }
    )
    report = UIDBasedComparator().compare_dataframes(source, target, uid_column="uid")

    types = set(report.mismatches["mismatch_type"].to_list())
    assert MismatchType.MISSING_IN_TARGET.value in types
    assert MismatchType.EXTRA_IN_TARGET.value in types
    assert MismatchType.VALUE_MISMATCH.value in types

    summary = report.summary
    assert summary[MismatchType.MISSING_IN_TARGET.value] == 1
    assert summary[MismatchType.EXTRA_IN_TARGET.value] == 1
    assert summary[MismatchType.VALUE_MISMATCH.value] == 1

    rows = report.row_dicts()
    assert len(rows) == 3
    vm = next(r for r in rows if r["mismatch_type"] == MismatchType.VALUE_MISMATCH.value)
    assert vm["uid"] == "b"
    assert vm["column_name"] == "x"
    assert vm["source_value"] == "2"
    assert vm["target_value"] == "9"
    assert vm.get("row_detail")
    detail = json.loads(vm["row_detail"])
    assert detail["source_record"]["x"] == 2
    assert detail["target_record"]["x"] == 9

    miss = next(r for r in rows if r["mismatch_type"] == MismatchType.MISSING_IN_TARGET.value)
    d2 = json.loads(miss["row_detail"])
    assert d2["source_record"]["uid"] == "c"
    assert d2["target_record"] is None

    extra = next(r for r in rows if r["mismatch_type"] == MismatchType.EXTRA_IN_TARGET.value)
    d3 = json.loads(extra["row_detail"])
    assert d3["source_record"] is None
    assert d3["target_record"]["uid"] == "d"


def test_null_eq_missing_no_value_mismatch():
    source = pl.DataFrame({"uid": ["a"], "x": [None]})
    target = pl.DataFrame({"uid": ["a"], "x": [None]})
    report = UIDBasedComparator().compare_dataframes(source, target, uid_column="uid")
    assert report.mismatches.is_empty()


def test_null_vs_value_is_mismatch():
    source = pl.DataFrame({"uid": ["a"], "x": [1]})
    target = pl.DataFrame({"uid": ["a"], "x": [None]})
    report = UIDBasedComparator().compare_dataframes(source, target, uid_column="uid")
    assert report.mismatches.height == 1
    r = report.row_dicts()[0]
    assert r["mismatch_type"] == MismatchType.VALUE_MISMATCH.value


def test_duplicate_uid_raises():
    source = pl.DataFrame({"uid": ["a", "a"], "x": [1, 2]})
    target = pl.DataFrame({"uid": ["a"], "x": [1]})
    with pytest.raises(UIDComparisonError):
        UIDBasedComparator().compare_dataframes(source, target, uid_column="uid")


def test_compare_columns_subset():
    source = pl.DataFrame({"uid": ["a"], "x": [1], "y": [10]})
    target = pl.DataFrame({"uid": ["a"], "x": [2], "y": [10]})
    report = UIDBasedComparator().compare_dataframes(
        source, target, uid_column="uid", compare_columns=["x"]
    )
    assert report.mismatches.height == 1
    assert report.row_dicts()[0]["column_name"] == "x"


def test_lazy_comparator_matches_dataframe_path():
    source = pl.DataFrame({"uid": ["a", "b"], "x": [1, 2]})
    target = pl.DataFrame({"uid": ["a"], "x": [1]})
    lazy_cmp = UIDKeyedLazyComparator()
    lf_out = lazy_cmp.compare(source.lazy(), target.lazy(), key_columns=["uid"])
    df_lazy = lf_out.collect()

    direct = UIDBasedComparator().compare_dataframes(source, target, uid_column="uid").mismatches
    df_lazy = df_lazy.sort("uid")
    direct = direct.sort("uid")
    assert df_lazy.shape == direct.shape


def test_lazy_comparator_requires_single_key():
    with pytest.raises(ComparisonError):
        UIDKeyedLazyComparator().compare(
            pl.DataFrame({"uid": [1]}).lazy(),
            pl.DataFrame({"uid": [1]}).lazy(),
            key_columns=["uid", "other"],
        )
