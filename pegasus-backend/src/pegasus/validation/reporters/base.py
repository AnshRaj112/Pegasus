"""Emit mismatch artifacts (files, metrics, tickets) from Polars results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import polars as pl


class MismatchReporter(ABC):
    """Serialize comparison output for humans or downstream systems."""

    @abstractmethod
    def report(
        self,
        mismatches: pl.LazyFrame | pl.DataFrame,
        *,
        destination: str | Path | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> Path | str:
        """Materialize *mismatches* to *destination* and return a locator string."""
        ...
