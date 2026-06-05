# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
# --- END GENERATED FILE METADATA ---

"""Fixed-width file streaming reader."""

from pathlib import Path
from typing import Any, Iterator

from category1.models.schemas import ColumnSchema, ConnectionConfig, DatasetSchema
from category1.readers.base import StreamingReader


class FixedWidthReader(StreamingReader):
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.file_path = Path(config.file_path or "")
        opts = config.file_options
        self.encoding = opts.get("encoding", "utf-8")
        self.column_specs: list[dict] = opts.get("column_specs", [])
        self.skip_lines = opts.get("skip_lines", 0)

    def get_schema(self) -> DatasetSchema:
        columns = []
        for i, spec in enumerate(self.column_specs):
            columns.append(ColumnSchema(
                name=spec["name"],
                data_type=spec.get("type", "string"),
                position=i,
            ))
        return DatasetSchema(columns=columns)

    def read_chunks(self, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
        schema = self.get_schema()
        chunk: list[dict[str, Any]] = []

        with open(self.file_path, encoding=self.encoding) as f:
            for _ in range(self.skip_lines):
                f.readline()
            for line in f:
                line = line.rstrip("\n\r")
                record = {}
                for spec in self.column_specs:
                    start = spec["start"]
                    end = spec.get("end", start + spec.get("width", 0))
                    record[spec["name"]] = line[start:end].strip()
                chunk.append(record)
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
        if chunk:
            yield chunk

    def get_row_count(self) -> int | None:
        count = 0
        with open(self.file_path, encoding=self.encoding) as f:
            for _ in range(self.skip_lines):
                f.readline()
            for _ in f:
                count += 1
        return count
