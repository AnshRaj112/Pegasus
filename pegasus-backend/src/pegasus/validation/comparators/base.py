"""Expected-vs-actual comparison contracts (logic intentionally deferred)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

import polars as pl


class ValidationComparator(ABC):
    """Compare two Polars pipelines and surface row-level mismatches.

    Concrete implementations will join on business keys, diff columns, and
    classify mismatch kinds. This base type only fixes the integration surface.
    """

    @abstractmethod
    def compare(
        self,
        expected: pl.LazyFrame,
        actual: pl.LazyFrame,
        *,
        key_columns: Sequence[str],
        compare_columns: Sequence[str] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> pl.LazyFrame:
        """Return a lazy frame describing mismatches (schema TBD per product rules).

        ``compare_columns`` defaults to "all non-key columns" in implementations.
        """
        ...
