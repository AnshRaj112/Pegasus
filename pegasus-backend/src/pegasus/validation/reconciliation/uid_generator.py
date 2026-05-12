"""UID generation helpers for reconciliation (deterministic SHA-256, composite keys)."""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from pegasus.validation.uids.sha256_composite import SHA256CompositeUIDGenerator

__all__ = [
    "SHA256CompositeUIDGenerator",
    "attach_composite_uid_column",
]


def attach_composite_uid_column(
    frame: pl.DataFrame,
    column_names: Sequence[str],
    *,
    output_column: str = "uid",
    generator: SHA256CompositeUIDGenerator | None = None,
) -> pl.DataFrame:
    """Materialize *output_column* on a chunk using :class:`SHA256CompositeUIDGenerator`.

    Typical use: build a stable ``uid`` column from multiple natural-key columns before
    reconciliation when callers prefer composite keys over a single CSV column.
    """
    gen = generator or SHA256CompositeUIDGenerator()
    out = gen.generate_uid_column(frame, list(column_names), output_column=output_column)
    assert isinstance(out, pl.DataFrame)
    return out
