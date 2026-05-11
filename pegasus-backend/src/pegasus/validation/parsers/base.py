"""Structural parsing of tabular frames (types, nesting, derived columns)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import polars as pl


class FrameParser(ABC):
    """Parse or reshape Polars frames while keeping lazy evaluation when possible."""

    @abstractmethod
    def parse(
        self,
        frame: pl.LazyFrame,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> pl.LazyFrame:
        """Return a new lazy frame with parsed / derived columns applied."""
        ...
