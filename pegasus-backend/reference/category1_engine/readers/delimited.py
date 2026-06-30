# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T05:26:24Z
# --- END GENERATED FILE METADATA ---

"""Streaming delimited file readers (CSV, TSV, PSV)."""

import csv
from pathlib import Path
from typing import Any, Iterator

from category1.models.schemas import ColumnSchema, ConnectionConfig, DatasetSchema, FileFormat
from category1.readers.base import StreamingReader


class DelimitedReader(StreamingReader):
    def __init__(self, config: ConnectionConfig, delimiter: str = ","):
        super().__init__(config)
        self.delimiter = delimiter
        self.file_path = Path(config.file_path or "")
        opts = config.file_options
        self.has_header = opts.get("has_header", True)
        self.encoding = opts.get("encoding", "utf-8")
        self.quotechar = opts.get("quotechar", '"')
        self._schema: DatasetSchema | None = None
        self._columns: list[str] = opts.get("columns", [])

    def get_schema(self) -> DatasetSchema:
        if self._schema:
            return self._schema
        columns: list[ColumnSchema] = []
        if self._columns:
            for i, name in enumerate(self._columns):
                columns.append(ColumnSchema(name=name, data_type="string", position=i))
        elif self.has_header:
            with open(self.file_path, encoding=self.encoding, newline="") as f:
                reader = csv.reader(f, delimiter=self.delimiter, quotechar=self.quotechar)
                header = next(reader, [])
                for i, name in enumerate(header):
                    columns.append(ColumnSchema(name=name.strip(), data_type="string", position=i))
        else:
            with open(self.file_path, encoding=self.encoding, newline="") as f:
                first = f.readline()
            count = len(first.split(self.delimiter))
            for i in range(count):
                columns.append(ColumnSchema(name=f"col_{i}", data_type="string", position=i))
        self._schema = DatasetSchema(columns=columns)
        return self._schema

    def read_chunks(self, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
        schema = self.get_schema()
        col_names = [c.name for c in schema.columns]
        chunk: list[dict[str, Any]] = []

        with open(self.file_path, encoding=self.encoding, newline="") as f:
            reader = csv.reader(f, delimiter=self.delimiter, quotechar=self.quotechar)
            if self.has_header:
                next(reader, None)
            for row in reader:
                record = {}
                for i, name in enumerate(col_names):
                    record[name] = row[i] if i < len(row) else None
                chunk.append(record)
                if len(chunk) >= chunk_size:
                    yield chunk
                    chunk = []
        if chunk:
            yield chunk

    def get_row_count(self) -> int | None:
        count = 0
        with open(self.file_path, encoding=self.encoding, newline="") as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            if self.has_header:
                next(reader, None)
            for _ in reader:
                count += 1
        return count


class CSVReader(DelimitedReader):
    def __init__(self, config: ConnectionConfig):
        super().__init__(config, delimiter=",")


class TSVReader(DelimitedReader):
    def __init__(self, config: ConnectionConfig):
        super().__init__(config, delimiter="\t")


class PSVReader(DelimitedReader):
    def __init__(self, config: ConnectionConfig):
        super().__init__(config, delimiter="|")
