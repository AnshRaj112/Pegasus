"""Deterministic hash partition routing for UID-keyed hash partitions (vectorized in Polars)."""

from __future__ import annotations

import logging
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

# Align with :class:`pegasus.validation.uids.sha256_composite.SHA256CompositeUIDGenerator`
# so single-column routing matches composite null semantics if callers mix approaches.
_DEFAULT_NULL_PLACEHOLDER = "__NULL__"


def canonical_uid_token(value: Any, *, null_placeholder: str = _DEFAULT_NULL_PLACEHOLDER) -> str:
    """Return the UTF-8 string used for partition routing.

    ``None`` maps to *null_placeholder* so nulls are stable and unambiguous.
    Other values use ``str(value)``.
    """
    if value is None:
        return null_placeholder
    return str(value)


def partition_bucket_from_uid_token(uid_token: str, buckets: int) -> int:
    """``partition_id = hash(uid_token) % buckets`` using Polars' deterministic :meth:`~polars.Series.hash`."""
    if buckets < 1:
        raise ValueError("buckets must be >= 1")
    s = pl.Series("uid", [uid_token], dtype=pl.Utf8)
    routed = (s.hash(seed=0) % buckets).cast(pl.Int64)
    return int(routed[0])


def add_sha256_two_level_partition_columns(
    batch: pl.DataFrame,
    uid_column: str,
    buckets: int,
    sub_buckets: int,
    *,
    null_placeholder: str = _DEFAULT_NULL_PLACEHOLDER,
) -> pl.DataFrame:
    """Append ``_pegasus_part`` and ``_pegasus_sub`` using two Polars hash seeds (fast, vectorized)."""
    if uid_column not in batch.columns:
        raise ValueError(f"uid_column {uid_column!r} not in batch columns: {batch.columns}")
    if sub_buckets < 1:
        raise ValueError("sub_buckets must be >= 1")
    tok = pl.col(uid_column).cast(pl.Utf8).fill_null(null_placeholder)
    part = (tok.hash(seed=0) % buckets).cast(pl.UInt32).alias("_pegasus_part")
    sub = (
        pl.when(pl.lit(sub_buckets > 1))
        .then((tok.hash(seed=1) % sub_buckets).cast(pl.UInt32))
        .otherwise(pl.lit(0, dtype=pl.UInt32))
        .alias("_pegasus_sub")
    )
    out = batch.with_columns(part, sub)
    logger.debug(
        "Two-level hash partition uid_column=%r buckets=%d sub=%d batch_rows=%d",
        uid_column,
        buckets,
        sub_buckets,
        batch.height,
    )
    return out


def add_sha256_partition_column(
    batch: pl.DataFrame,
    uid_column: str,
    buckets: int,
    *,
    null_placeholder: str = _DEFAULT_NULL_PLACEHOLDER,
) -> pl.DataFrame:
    """Append ``_pegasus_part`` with ``hash(uid_token) % buckets`` (vectorized; no per-row Python loops)."""
    if uid_column not in batch.columns:
        raise ValueError(f"uid_column {uid_column!r} not in batch columns: {batch.columns}")
    tok = pl.col(uid_column).cast(pl.Utf8).fill_null(null_placeholder)
    logger.debug(
        "Hash partition column uid_column=%r buckets=%d batch_rows=%d",
        uid_column,
        buckets,
        batch.height,
    )
    return batch.with_columns((tok.hash(seed=0) % buckets).cast(pl.UInt32).alias("_pegasus_part"))
