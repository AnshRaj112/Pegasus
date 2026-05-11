"""Stable identifiers for rows or logical records prior to comparison."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl


class UIDGenerator(ABC):
    """Add a deterministic identifier column derived from one or more source columns."""

    @abstractmethod
    def generate_uid_column(
        self,
        frame: pl.DataFrame | pl.LazyFrame,
        column_names: Sequence[str],
        *,
        output_column: str = "uid",
        context: Mapping[str, Any] | None = None,
    ) -> pl.DataFrame | pl.LazyFrame:
        """Return *frame* with *output_column* containing a stable UID per row.

        Implementations should treat *column_names* order as part of the composite
        key (``customer_id`` + ``order_id`` + ``date`` is distinct from permutations).
        """
        ...
