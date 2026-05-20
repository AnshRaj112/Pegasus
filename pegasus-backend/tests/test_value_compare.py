"""Tests for semantic value comparison."""

from __future__ import annotations

import polars as pl
import pytest

from pegasus.validation.comparators import UIDBasedComparator
from pegasus.validation.value_compare import (
    try_parse_calendar_date,
    values_equal_for_validation,
)


def test_cross_format_dates_equal() -> None:
    assert values_equal_for_validation("14-04-1960", "1960-04-14")
    assert try_parse_calendar_date("14-04-1960") == try_parse_calendar_date("1960-04-14")


def test_different_dates_not_equal() -> None:
    assert not values_equal_for_validation("14-04-1960", "1960-04-15")


def test_uid_comparator_treats_cross_format_dob_as_match() -> None:
    source = pl.DataFrame(
        {
            "id": ["1"],
            "Name": ["User1"],
            "Email": ["user1@example.com"],
            "DOB": ["14-04-1960"],
        }
    )
    target = pl.DataFrame(
        {
            "id": ["1"],
            "Name": ["User1"],
            "Email": ["user1@example.com"],
            "DOB": ["1960-04-14"],
        }
    )
    report = UIDBasedComparator().compare_dataframes(source, target, uid_column="id")
    assert report.mismatches.is_empty()
    assert report.summary.get("value_mismatch", 0) == 0
