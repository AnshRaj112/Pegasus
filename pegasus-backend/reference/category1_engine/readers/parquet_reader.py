# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:21:21Z
# --- END GENERATED FILE METADATA ---

"""Parquet streaming reader — native pure-Python implementation."""

from pathlib import Path
from typing import Any, Iterator

from category1.models.schemas import ColumnSchema, ConnectionConfig, DatasetSchema
from category1.readers.base import StreamingReader
from category1.readers.native.parquet_file import NativeParquetFile


class ParquetReader(StreamingReader):
    """Reads Parquet row groups via the in-house native decoder."""

    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.file_path = Path(config.file_path or "")
        self._file: NativeParquetFile | None = None

    def _get_file(self) -> NativeParquetFile:
        if self._file is None:
            self._file = NativeParquetFile(self.file_path)
        return self._file

    def get_schema(self) -> DatasetSchema:
        pf = self._get_file()
        columns = [
            ColumnSchema(
                name=col.name,
                data_type=pf.schema_type_names()[i] if i < len(pf.schema_type_names()) else "string",
                position=i,
            )
            for i, col in enumerate(pf.schema_columns())
        ]
        return DatasetSchema(columns=columns, row_count=pf.num_rows)

    def read_chunks(self, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
        pf = self._get_file()
        chunk: list[dict[str, Any]] = []
        for row_group in pf.iter_row_groups():
            for record in row_group:
                chunk.append(record)
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
        if chunk:
            yield chunk

    def get_row_count(self) -> int | None:
        return self._get_file().num_rows
