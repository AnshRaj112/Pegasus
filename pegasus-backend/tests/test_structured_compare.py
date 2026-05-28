"""Tests for structured literal cell comparison."""

from __future__ import annotations

import polars as pl

from pegasus.schemas.validation import ColumnMapping
from pegasus.validation.compare_rules import build_rules_by_source_column, values_equal_with_rule
from pegasus.validation.comparators import UIDBasedComparator
from pegasus.validation.structured_compare import structured_strings_equal


def test_ignore_order_list_and_dict() -> None:
    assert structured_strings_equal("[3, 1, 2]", "[2, 1, 3]", order_sensitive=False)
    assert structured_strings_equal('{"b": 2, "a": 1}', '{"a": 1, "b": 2}', order_sensitive=False)


def test_strict_order_list_and_dict() -> None:
    assert not structured_strings_equal("[3, 1, 2]", "[2, 1, 3]", order_sensitive=True)
    assert structured_strings_equal("[1, 2, 3]", "[1, 2, 3]", order_sensitive=True)
    assert not structured_strings_equal('{"b": 2, "a": 1}', '{"a": 1, "b": 2}', order_sensitive=True)


def test_spelling_mismatch_always_fails() -> None:
    assert not structured_strings_equal('["alpha"]', '["beta"]', order_sensitive=False)
    assert not structured_strings_equal('["alpha"]', '["beta"]', order_sensitive=True)


def test_python_literal_tuple() -> None:
    assert structured_strings_equal("(1, 2)", "(2, 1)", order_sensitive=False)
    assert not structured_strings_equal("(1, 2)", "(2, 1)", order_sensitive=True)


def test_compare_rule_mapping() -> None:
    mapping = ColumnMapping(
        source_column="tags",
        target_column="tags",
        compare_mode="structured",
        structured_order_sensitive=False,
    )
    rule = build_rules_by_source_column([mapping])["tags"]
    assert values_equal_with_rule('["a", "b"]', '["b", "a"]', rule)


def test_uid_comparator_structured_column() -> None:
    mapping = ColumnMapping(
        source_column="payload",
        target_column="payload",
        compare_mode="structured",
    )
    rules = build_rules_by_source_column([mapping])
    source = pl.DataFrame({"id": ["1"], "payload": ['{"x": [1, 2]}']})
    target = pl.DataFrame({"id": ["1"], "payload": ['{"x": [2, 1]}']})
    report = UIDBasedComparator().compare_dataframes(
        source,
        target,
        uid_column="id",
        compare_rules=rules,
    )
    assert report.mismatches.is_empty()
