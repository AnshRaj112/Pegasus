# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:17:42Z
# --- END GENERATED FILE METADATA ---

"""Avro streaming reader using fastavro."""

from pathlib import Path
from typing import Any, Iterator

import fastavro

from category1.models.schemas import ColumnSchema, ConnectionConfig, DatasetSchema
from category1.readers.base import StreamingReader


class AvroReader(StreamingReader):
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.file_path = Path(config.file_path or "")

    def get_schema(self) -> DatasetSchema:
        with open(self.file_path, "rb") as f:
            avro_reader = fastavro.reader(f)
            columns = []
            for i, field in enumerate(avro_reader.writer_schema.get("fields", [])):
                columns.append(ColumnSchema(
                    name=field["name"],
                    data_type=str(field.get("type", "string")),
                    position=i,
                ))
        return DatasetSchema(columns=columns)

    def read_chunks(self, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
        chunk: list[dict[str, Any]] = []
        with open(self.file_path, "rb") as f:
            for record in fastavro.reader(f):
                chunk.append(dict(record))
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
        if chunk:
            yield chunk
