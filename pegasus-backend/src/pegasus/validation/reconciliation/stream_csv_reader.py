"""Streaming CSV reader facade for the external-memory reconciliation engine."""

from __future__ import annotations

from pegasus.validation.readers.polars_csv_reader import PolarsCSVReader


class StreamCSVReader(PolarsCSVReader):
    """Chunked UTF-8 CSV ingestion built on Polars lazy scans and ``collect_batches``.

    This type is the reconciliation-layer name for :class:`PolarsCSVReader`: configurable
    batch sizes, delimiter and encoding via ``read_options``, and iterator-style batch
    delivery so callers never hold a full file in RAM.

    See :class:`PolarsCSVReader` for parameters and method documentation.
    """

    __slots__ = ()
