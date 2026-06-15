# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:43:26Z
# --- END GENERATED FILE METADATA ---

"""Native Parquet file reader — reads row groups without external columnar libraries."""

import struct
from pathlib import Path
from typing import Any, Iterator

from category1.readers.native.parquet_decoder import ColumnPageDecoder
from category1.readers.native.parquet_format import (
    TYPE_NAMES,
    ParquetMetadata,
    SchemaColumn,
    parse_file_metadata,
)


class NativeParquetFile:
    MAGIC = b"PAR1"

    def __init__(self, path: Path):
        self.path = path
        self._metadata: ParquetMetadata | None = None
        self._file_size: int = 0

    @property
    def metadata(self) -> ParquetMetadata:
        if self._metadata is None:
            self._load_footer()
        return self._metadata

    def _load_footer(self) -> None:
        with open(self.path, "rb") as f:
            f.seek(0, 2)
            self._file_size = f.tell()
            if self._file_size < 8:
                raise ValueError("File too small to be Parquet")
            f.seek(-8, 2)
            tail = f.read(8)
            if tail[4:] != self.MAGIC:
                raise ValueError("Invalid Parquet magic bytes")
            footer_len = struct.unpack("<I", tail[:4])[0]
            f.seek(-(footer_len + 8), 2)
            footer_data = f.read(footer_len)
        self._metadata = parse_file_metadata(footer_data)

    def num_row_groups(self) -> int:
        return len(self.metadata.row_groups)

    def read_row_group(self, rg_index: int) -> list[dict[str, Any]]:
        meta = self.metadata
        if rg_index >= len(meta.row_groups):
            return []
        rg = meta.row_groups[rg_index]
        schema = meta.schema
        column_data: list[list[Any]] = []

        with open(self.path, "rb") as f:
            for col_idx, chunk in enumerate(rg.columns):
                col_schema = schema[col_idx] if col_idx < len(schema) else schema[-1]
                read_size = chunk.meta.total_compressed_size or chunk.meta.total_uncompressed_size
                f.seek(chunk.file_offset + chunk.meta.data_page_offset)
                chunk_data = f.read(read_size)
                if not chunk_data:
                    f.seek(chunk.file_offset)
                    chunk_data = f.read(read_size)

                decoder = ColumnPageDecoder(col_schema)
                values = decoder.decode_chunk(chunk_data, chunk.meta.codec)
                column_data.append(values)

        if not column_data:
            return []

        num_rows = max(len(c) for c in column_data)
        records: list[dict[str, Any]] = []
        col_names = [c.name for c in schema]
        for i in range(num_rows):
            record = {}
            for j, name in enumerate(col_names):
                vals = column_data[j] if j < len(column_data) else []
                record[name] = vals[i] if i < len(vals) else None
            records.append(record)
        return records

    def iter_row_groups(self) -> Iterator[list[dict[str, Any]]]:
        for i in range(self.num_row_groups()):
            yield self.read_row_group(i)

    def schema_columns(self) -> list[SchemaColumn]:
        return self.metadata.schema

    def schema_type_names(self) -> list[str]:
        return [TYPE_NAMES.get(c.physical_type, "string") for c in self.metadata.schema]

    @property
    def num_rows(self) -> int:
        return self.metadata.num_rows
