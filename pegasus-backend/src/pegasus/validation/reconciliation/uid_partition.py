"""Deterministic SHA-256 partition routing for UID-keyed hash partitions."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)

# Align with :class:`pegasus.validation.uids.sha256_composite.SHA256CompositeUIDGenerator`
# so single-column routing matches composite null semantics if callers mix approaches.
_DEFAULT_NULL_PLACEHOLDER = "__NULL__"


def canonical_uid_token(value: Any, *, null_placeholder: str = _DEFAULT_NULL_PLACEHOLDER) -> str:
    """Return the UTF-8 string fed into SHA-256 for partition routing.

    ``None`` maps to *null_placeholder* so nulls are stable and unambiguous.
    Other values use ``str(value)`` (Unicode, replacement on encode only at hash time).
    """
    if value is None:
        return null_placeholder
    return str(value)


def partition_bucket_from_uid_token(uid_token: str, buckets: int) -> int:
    """``partition_id = int(sha256(uid_token))[:8] % buckets`` (stable across processes)."""
    if buckets < 1:
        raise ValueError("buckets must be >= 1")
    digest = hashlib.sha256(uid_token.encode("utf-8", errors="replace")).digest()
    return int.from_bytes(digest[:8], "big") % buckets


def _partition_series(uid: pl.Series, buckets: int, *, null_placeholder: str) -> pl.Series:
    out: list[int] = []
    for x in uid.to_list():
        tok = canonical_uid_token(x, null_placeholder=null_placeholder)
        out.append(partition_bucket_from_uid_token(tok, buckets))
    return pl.Series("_pegasus_part", out, dtype=pl.UInt32)


def add_sha256_two_level_partition_columns(
    batch: pl.DataFrame,
    uid_column: str,
    buckets: int,
    sub_buckets: int,
    *,
    null_placeholder: str = _DEFAULT_NULL_PLACEHOLDER,
) -> pl.DataFrame:
    """Append ``_pegasus_part`` and ``_pegasus_sub`` using one SHA-256 digest per row.

    ``_pegasus_part`` uses digest bytes 0–7 (same as :func:`partition_bucket_from_uid_token`);
    ``_pegasus_sub`` uses bytes 8–15 modulo *sub_buckets* (ignored downstream when *sub_buckets* is 1).
    """
    if uid_column not in batch.columns:
        raise ValueError(f"uid_column {uid_column!r} not in batch columns: {batch.columns}")
    if sub_buckets < 1:
        raise ValueError("sub_buckets must be >= 1")
    parts: list[int] = []
    subs: list[int] = []
    for x in batch[uid_column].to_list():
        tok = canonical_uid_token(x, null_placeholder=null_placeholder)
        d = hashlib.sha256(tok.encode("utf-8", errors="replace")).digest()
        parts.append(int.from_bytes(d[:8], "big") % buckets)
        subs.append(int.from_bytes(d[8:16], "big") % sub_buckets if sub_buckets > 1 else 0)
    out = batch.with_columns(
        pl.Series("_pegasus_part", parts, dtype=pl.UInt32),
        pl.Series("_pegasus_sub", subs, dtype=pl.UInt32),
    )
    logger.debug(
        "Two-level SHA256 partition uid_column=%r buckets=%d sub=%d batch_rows=%d",
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
    """Append ``_pegasus_part`` with ``partition_bucket_from_uid_token`` for each row.

    Uses :func:`polars.Expr.map_batches` on the UID column so routing stays in Polars
    chunk space (no full-file materialization beyond the current batch).
    """
    if uid_column not in batch.columns:
        raise ValueError(f"uid_column {uid_column!r} not in batch columns: {batch.columns}")

    def _map_uid(s: pl.Series) -> pl.Series:
        return _partition_series(s, buckets, null_placeholder=null_placeholder)

    logger.debug(
        "SHA256 partition column uid_column=%r buckets=%d batch_rows=%d",
        uid_column,
        buckets,
        batch.height,
    )
    return batch.with_columns(
        pl.col(uid_column).map_batches(_map_uid, return_dtype=pl.UInt32).alias("_pegasus_part")
    )
