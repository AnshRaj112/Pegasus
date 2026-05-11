"""Deterministic SHA-256 UIDs from composite Polars columns."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl
import polars.exceptions as pl_exc

from pegasus.validation.uids.base import UIDGenerator
from pegasus.validation.uids.exceptions import (
    UIDColumnNotFoundError,
    UIDConfigurationError,
    UIDGeneratorError,
)

logger = logging.getLogger(__name__)


def _sha256_hex_series(payload: pl.Series) -> pl.Series:
    """Hex SHA-256 of each UTF-8 payload string (64 hex chars per row)."""
    out: list[str] = []
    for x in payload.to_list():
        if x is None:
            raw = b""
        else:
            raw = str(x).encode("utf-8", errors="replace")
        out.append(hashlib.sha256(raw).hexdigest())
    return pl.Series(payload.name, out, dtype=pl.String)


class SHA256CompositeUIDGenerator(UIDGenerator):
    """Build ``uid = SHA256( col1 || sep || col2 || ... )`` with null-safe string parts.

    Each source column is cast to string, nulls replaced with a fixed placeholder so
    null and the literal placeholder string remain distinguishable when desired.

    Parameters
    ----------
    separator
        Delimiter inserted between column string forms (default ``"|"``).
    null_placeholder
        String substituted for null values before concatenation.
    """

    __slots__ = ("_null_placeholder", "_separator")

    def __init__(
        self,
        *,
        separator: str = "|",
        null_placeholder: str = "__NULL__",
    ) -> None:
        if not separator:
            raise UIDConfigurationError("separator must be a non-empty string")
        if null_placeholder == "":
            raise UIDConfigurationError("null_placeholder must be non-empty to keep nulls unambiguous")
        self._separator = separator
        self._null_placeholder = null_placeholder

    def generate_uid_column(
        self,
        frame: pl.DataFrame | pl.LazyFrame,
        column_names: Sequence[str],
        *,
        output_column: str = "uid",
        context: Mapping[str, Any] | None = None,
    ) -> pl.DataFrame | pl.LazyFrame:
        """Append *output_column* with lower-case hex SHA-256 of the composite string.

        The composite string is built as::

            concat( cast(col_i, String).fill_null(null_placeholder), separator=separator )

        then hashed with SHA-256. The same input rows always yield the same UID.

        Parameters
        ----------
        frame
            Polars frame to extend.
        column_names
            Ordered columns included in the UID (order matters).
        output_column
            Name of the new column (must not already exist on *frame*).
        context
            Reserved for future options (ignored).

        Returns
        -------
        polars.DataFrame | polars.LazyFrame
            Same concrete type as *frame*.

        Raises
        ------
        UIDConfigurationError
            If ``column_names`` is empty or *output_column* already exists.
        UIDColumnNotFoundError
            If any name in ``column_names`` is missing from the schema.
        UIDGeneratorError
            If Polars fails while building the expression.
        """
        _ = context
        if not column_names:
            raise UIDConfigurationError("column_names must contain at least one column")

        schema = frame.collect_schema() if isinstance(frame, pl.LazyFrame) else frame.schema
        missing = [name for name in column_names if name not in schema]
        if missing:
            logger.warning("UID source columns missing from schema: %s", missing)
            raise UIDColumnNotFoundError(f"Unknown columns for UID: {missing}")

        if output_column in schema:
            raise UIDConfigurationError(
                f"Output column {output_column!r} already exists; choose a different output_column"
            )

        parts: list[pl.Expr] = [
            pl.col(name).cast(pl.String).fill_null(self._null_placeholder) for name in column_names
        ]
        payload = pl.concat_str(parts, separator=self._separator)
        uid_expr = payload.map_batches(
            _sha256_hex_series,
            return_dtype=pl.String,
            is_elementwise=True,
        ).alias(output_column)

        logger.debug(
            "Building SHA256 UID column=%r from columns=%s",
            output_column,
            list(column_names),
        )
        try:
            return frame.with_columns(uid_expr)
        except pl_exc.PolarsError as exc:
            logger.exception("Polars failed while adding UID column")
            raise UIDGeneratorError("Failed to add UID column") from exc
