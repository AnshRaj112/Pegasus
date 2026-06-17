# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:46:02Z
# --- END GENERATED FILE METADATA ---

"""ORC streaming reader — native pure-Python implementation."""

from pathlib import Path
from typing import Any, Iterator

from category1.models.schemas import ColumnSchema, ConnectionConfig, DatasetSchema
from category1.readers.base import StreamingReader
from category1.readers.native.orc_file import NativeOrcFile


class ORCReader(StreamingReader):
    """Reads ORC stripes via the in-house native decoder."""

    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.file_path = Path(config.file_path or "")

    def _get_file(self) -> NativeOrcFile:
        return NativeOrcFile(self.file_path)

    def get_schema(self) -> DatasetSchema:
        orc = self._get_file()
        columns = [
            ColumnSchema(name=name, data_type=dtype, position=i)
            for i, (name, dtype) in enumerate(orc.schema_columns())
        ]
        return DatasetSchema(columns=columns, row_count=orc.num_rows)

    def read_chunks(self, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
        orc = self._get_file()
        chunk: list[dict[str, Any]] = []
        for stripe in orc.iter_stripes():
            for record in stripe:
                chunk.append(record)
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
        if chunk:
            yield chunk

    def get_row_count(self) -> int | None:
        return self._get_file().num_rows
