"""Canonicalization rules prior to comparison."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import polars as pl


class Normalizer(ABC):
    """Apply deterministic transforms (trim, casing, rounding, etc.)."""

    @abstractmethod
    def normalize(
        self,
        frame: pl.LazyFrame,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> pl.LazyFrame:
        """Return a lazy frame with normalization rules applied."""
        ...
