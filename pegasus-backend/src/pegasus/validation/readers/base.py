"""CSV ingestion behind a single abstraction (streaming-friendly)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import polars as pl


class CSVReader(ABC):
    """Read CSV sources as Polars batches without loading the full file eagerly.

    Implementations should prefer :func:`polars.scan_csv` / batched collection patterns
    so large files stay bounded in memory. Callers iterate :meth:`iter_batches` and
    never assume the full dataset is materialized.
    """

    @abstractmethod
    def iter_batches(
        self,
        path: str | Path,
        *,
        batch_size: int | None = None,
        schema_overrides: Mapping[str, Any] | None = None,
        read_options: Mapping[str, Any] | None = None,
    ) -> Iterator[pl.DataFrame]:
        """Yield successive Polars ``DataFrame`` chunks from *path*.

        Parameters
        ----------
        path:
            CSV location (local path today; object storage URIs later).
        batch_size:
            Target rows per batch; ``None`` lets the implementation choose.
        schema_overrides:
            Optional Polars dtypes for named columns.
        read_options:
            Forward-compatible bag for ``scan_csv`` / ``read_csv`` kwargs
            (e.g. ``separator``, ``quote_char``, ``null_values``).
        """
        ...

    @abstractmethod
    def scan(self, path: str | Path, *, read_options: Mapping[str, Any] | None = None) -> pl.LazyFrame:
        """Return a lazy frame for SQL-style or deferred transforms on CSV *path*.

        Implementations should build on :func:`polars.scan_csv` so streaming
        collection remains possible downstream.
        """
        ...
