"""Tests for :class:`SHA256CompositeUIDGenerator`."""

from __future__ import annotations

import hashlib

import polars as pl
import pytest

from pegasus.validation.uids import (
    SHA256CompositeUIDGenerator,
    UIDColumnNotFoundError,
    UIDConfigurationError,
)


def _expected_uid(*parts: str, sep: str = "|") -> str:
    payload = sep.join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_generate_uid_column_deterministic():
    gen = SHA256CompositeUIDGenerator(separator="|", null_placeholder="__NULL__")
    df = pl.DataFrame(
        {
            "customer_id": [1, 2, None],
            "order_id": [10, 10, 10],
            "date": ["2024-01-01", "2024-01-01", "2024-01-02"],
        }
    )
    out = gen.generate_uid_column(df, ["customer_id", "order_id", "date"], output_column="uid")

    assert out["uid"][0] == _expected_uid("1", "10", "2024-01-01")
    assert out["uid"][1] == _expected_uid("2", "10", "2024-01-01")
    assert out["uid"][2] == _expected_uid("__NULL__", "10", "2024-01-02")


def test_lazy_frame_same_uids():
    gen = SHA256CompositeUIDGenerator()
    df = pl.DataFrame({"a": [1], "b": [2]})
    lazy_uids = gen.generate_uid_column(df.lazy(), ["a", "b"], output_column="uid").collect()["uid"]
    eager_uids = gen.generate_uid_column(df, ["a", "b"], output_column="uid")["uid"]
    assert lazy_uids.to_list() == eager_uids.to_list()


def test_column_order_matters():
    gen = SHA256CompositeUIDGenerator()
    df = pl.DataFrame({"x": [1], "y": [2]})
    u1 = gen.generate_uid_column(df, ["x", "y"], output_column="uid")["uid"][0]
    u2 = gen.generate_uid_column(df, ["y", "x"], output_column="uid")["uid"][0]
    assert u1 != u2


def test_missing_column_raises():
    gen = SHA256CompositeUIDGenerator()
    df = pl.DataFrame({"a": [1]})
    with pytest.raises(UIDColumnNotFoundError):
        gen.generate_uid_column(df, ["a", "missing"])


def test_empty_columns_raises():
    gen = SHA256CompositeUIDGenerator()
    df = pl.DataFrame({"a": [1]})
    with pytest.raises(UIDConfigurationError):
        gen.generate_uid_column(df, [], output_column="uid")


def test_duplicate_output_column_raises():
    gen = SHA256CompositeUIDGenerator()
    df = pl.DataFrame({"a": [1], "uid": ["x"]})
    with pytest.raises(UIDConfigurationError):
        gen.generate_uid_column(df, ["a"], output_column="uid")
