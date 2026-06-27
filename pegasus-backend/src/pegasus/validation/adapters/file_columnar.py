# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-27T14:34:06Z
# --- END GENERATED FILE METADATA ---

"""Columnar file adapter (Parquet, ORC, Avro, Excel) with batched streaming."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import polars as pl
import pyarrow.parquet as pq

from pegasus.validation.adapters.base import TabularColumn, TabularSchema
from pegasus.validation.readers.pyarrow_io import (
    batch_to_dicts,
    iter_orc_batches,
    iter_parquet_batches,
    read_parquet_table,
    table_to_polars,
)


class FileColumnarAdapter:
    """Lazy/batched columnar reader using PyArrow (Parquet/ORC) and Polars (Excel/Avro)."""

    __slots__ = ("path", "_file_format", "_schema_cache")

    def __init__(self, path: Path, *, file_format: str = "parquet") -> None:
        self.path = Path(path)
        self._file_format = file_format.lower().strip().lstrip(".")
        self._schema_cache: TabularSchema | None = None

    def _parquet_schema(self) -> TabularSchema:
        schema = pq.read_schema(self.path)
        return TabularSchema(
            columns=[
                TabularColumn(name=str(name), data_type=str(schema.field(name).type))
                for name in schema.names
            ]
        )

    def _polars_schema(self, frame: pl.DataFrame) -> TabularSchema:
        return TabularSchema(
            columns=[TabularColumn(name=n, data_type=str(t)) for n, t in frame.schema.items()]
        )

    def _avro_frame(self) -> pl.DataFrame:
        import fastavro

        rows: list[dict[str, Any]] = []
        with open(self.path, "rb") as f:
            for record in fastavro.reader(f):
                rows.append(dict(record))
        return pl.DataFrame(rows) if rows else pl.DataFrame()

    def get_schema(self) -> TabularSchema:
        if self._schema_cache is not None:
            return self._schema_cache

        fmt = self._file_format
        if fmt in ("parquet", "pq"):
            self._schema_cache = self._parquet_schema()
        elif fmt == "orc":
            from pegasus.validation.readers.pyarrow_io import read_orc_table

            table = read_orc_table(self.path)
            self._schema_cache = TabularSchema(
                columns=[
                    TabularColumn(name=str(name), data_type=str(table.schema.field(name).type))
                    for name in table.column_names
                ]
            )
        elif fmt in ("excel", "xlsx", "xls"):
            self._schema_cache = self._polars_schema(pl.read_excel(self.path))
        elif fmt == "avro":
            self._schema_cache = self._polars_schema(self._avro_frame())
        else:
            self._schema_cache = self._parquet_schema()
        return self._schema_cache

    def get_row_count(self) -> int | None:
        return None

    def stream_records(self, chunk_rows: int) -> Iterator[list[dict[str, Any]]]:
        fmt = self._file_format
        batch_size = max(1, chunk_rows)

        if fmt in ("parquet", "pq"):
            for batch in iter_parquet_batches(self.path, batch_size=batch_size):
                records = batch_to_dicts(batch)
                if records:
                    yield records
            return

        if fmt == "orc":
            for batch in iter_orc_batches(self.path, batch_size=batch_size):
                records = batch_to_dicts(batch)
                if records:
                    yield records
            return

        if fmt in ("excel", "xlsx", "xls"):
            frame = pl.read_excel(self.path)
        elif fmt == "avro":
            frame = self._avro_frame()
        else:
            frame = table_to_polars(read_parquet_table(self.path))

        offset = 0
        while offset < frame.height:
            chunk = frame.slice(offset, batch_size)
            if chunk.is_empty():
                break
            yield chunk.to_dicts()
            offset += batch_size
