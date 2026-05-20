"""Tests for per-column compare rules."""

from __future__ import annotations

import polars as pl

from pegasus.schemas.validation import ColumnMapping
from pegasus.validation.compare_rules import build_rules_by_source_column, values_equal_with_rule
from pegasus.validation.comparators import UIDBasedComparator


def test_phone_strip_prefix_rule() -> None:
    mapping = ColumnMapping(
        source_column="mobile",
        target_column="mobile",
        compare_mode="phone",
        source_strip_prefix="+91",
    )
    rule = build_rules_by_source_column([mapping])["mobile"]
    assert values_equal_with_rule("+919876543210", "9876543210", rule)


def test_date_explicit_formats() -> None:
    mapping = ColumnMapping(
        source_column="DOB",
        target_column="DOB",
        compare_mode="date",
        source_date_format="%Y-%m-%d",
        target_date_format="%d-%m-%Y",
    )
    rule = build_rules_by_source_column([mapping])["DOB"]
    assert values_equal_with_rule("1960-04-14", "14-04-1960", rule)


def test_uid_comparator_with_phone_rule() -> None:
    mapping = ColumnMapping(
        source_column="mobile",
        target_column="mobile",
        compare_mode="phone",
        source_strip_prefix="+91",
    )
    source = pl.DataFrame({"id": ["1"], "mobile": ["+919876543210"]})
    target = pl.DataFrame({"id": ["1"], "mobile": ["9876543210"]})
    report = UIDBasedComparator().compare_dataframes(
        source,
        target,
        uid_column="id",
        compare_rules=build_rules_by_source_column([mapping]),
    )
    assert report.mismatches.is_empty()
