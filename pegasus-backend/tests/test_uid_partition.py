"""Tests for SHA-256 hash partition routing (uid_partition)."""

from __future__ import annotations

import polars as pl

from pegasus.validation.reconciliation.uid_partition import (
    add_sha256_partition_column,
    canonical_uid_token,
    partition_bucket_from_uid_token,
)


def test_partition_bucket_stable() -> None:
    assert partition_bucket_from_uid_token("abc", 16) == partition_bucket_from_uid_token("abc", 16)
    assert 0 <= partition_bucket_from_uid_token("x", 7) < 7


def test_canonical_uid_token_null_placeholder() -> None:
    assert canonical_uid_token(None) == "__NULL__"
    assert canonical_uid_token("a") == "a"


def test_add_sha256_partition_column_matches_row_level() -> None:
    buckets = 11
    df = pl.DataFrame({"uid": ["a", None, "b"]})
    out = add_sha256_partition_column(df, "uid", buckets)
    expected = [
        partition_bucket_from_uid_token(canonical_uid_token("a"), buckets),
        partition_bucket_from_uid_token(canonical_uid_token(None), buckets),
        partition_bucket_from_uid_token(canonical_uid_token("b"), buckets),
    ]
    assert out["_pegasus_part"].to_list() == expected


def test_two_level_partition_sub_range() -> None:
    from pegasus.validation.reconciliation.uid_partition import add_sha256_two_level_partition_columns

    buckets, sub = 8, 4
    df = pl.DataFrame({"uid": ["x", "y", None]})
    out = add_sha256_two_level_partition_columns(df, "uid", buckets, sub)
    assert out["_pegasus_part"].to_list() == [
        partition_bucket_from_uid_token(canonical_uid_token("x"), buckets),
        partition_bucket_from_uid_token(canonical_uid_token("y"), buckets),
        partition_bucket_from_uid_token(canonical_uid_token(None), buckets),
    ]
    for s in out["_pegasus_sub"].to_list():
        assert 0 <= s < sub
