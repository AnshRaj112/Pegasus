# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T10:16:15Z
# --- END GENERATED FILE METADATA ---

"""Parquet format constants and metadata parsing."""

from dataclasses import dataclass, field
from typing import Any

from category1.readers.native.thrift_compact import ThriftCompactReader

# Physical types (parquet.thrift Type enum)
PARQUET_BOOLEAN = 0
PARQUET_INT32 = 1
PARQUET_INT64 = 2
PARQUET_INT96 = 3
PARQUET_FLOAT = 4
PARQUET_DOUBLE = 5
PARQUET_BYTE_ARRAY = 6
PARQUET_FIXED_LEN_BYTE_ARRAY = 7

# Compression codecs
UNCOMPRESSED = 0
SNAPPY = 1
GZIP = 2
LZO = 3
BROTLI = 4
LZ4 = 5
ZSTD = 6

# Page types
DATA_PAGE = 0
INDEX_PAGE = 1
DICTIONARY_PAGE = 2
DATA_PAGE_V2 = 3

# Encodings
PLAIN = 0
PLAIN_DICTIONARY = 2
RLE = 3
BIT_PACKED = 4
DELTA_BINARY_PACKED = 5
DELTA_LENGTH_BYTE_ARRAY = 6
DELTA_BYTE_ARRAY = 7
RLE_DICTIONARY = 8

TYPE_NAMES = {
    PARQUET_BOOLEAN: "boolean",
    PARQUET_INT32: "int32",
    PARQUET_INT64: "int64",
    PARQUET_INT96: "timestamp",
    PARQUET_FLOAT: "float",
    PARQUET_DOUBLE: "double",
    PARQUET_BYTE_ARRAY: "string",
    PARQUET_FIXED_LEN_BYTE_ARRAY: "fixed",
}


@dataclass
class SchemaColumn:
    name: str
    physical_type: int
    type_length: int = 0
    max_definition_level: int = 0
    max_repetition_level: int = 0
    converted_type: int | None = None


@dataclass
class ColumnMeta:
    type: int
    path_in_schema: list[str]
    codec: int
    num_values: int
    total_uncompressed_size: int
    total_compressed_size: int
    data_page_offset: int
    dictionary_page_offset: int = 0
    encodings: list[int] = field(default_factory=list)


@dataclass
class ColumnChunkInfo:
    file_offset: int
    meta: ColumnMeta


@dataclass
class RowGroupInfo:
    num_rows: int
    total_byte_size: int
    columns: list[ColumnChunkInfo]


@dataclass
class ParquetMetadata:
    version: int
    num_rows: int
    schema: list[SchemaColumn]
    row_groups: list[RowGroupInfo]


def _parse_schema_elements(elements: list[dict]) -> list[SchemaColumn]:
    """Flatten nested schema tree into leaf columns with definition levels."""
    columns: list[SchemaColumn] = []

    def walk(idx: int, def_level: int, rep_level: int) -> int:
        elem = elements[idx]
        name = elem.get(4, b"").decode("utf-8", errors="replace")
        num_children = elem.get(5, 0)
        physical_type = elem.get(1)
        repetition = elem.get(3, 0)  # 0=REQUIRED, 1=OPTIONAL, 2=REPEATED

        if num_children:
            next_idx = idx + 1
            for _ in range(num_children):
                child = elements[next_idx]
                child_rep = child.get(3, 0)
                child_def = def_level + 1 if child_rep in (1, 2) else def_level
                child_rep_level = rep_level + 1 if child_rep == 2 else rep_level
                next_idx = walk(next_idx, child_def, child_rep_level)
            return next_idx

        if physical_type is not None:
            columns.append(SchemaColumn(
                name=name,
                physical_type=physical_type,
                type_length=elem.get(2, 0),
                max_definition_level=def_level,
                max_repetition_level=rep_level,
                converted_type=elem.get(6),
            ))
        return idx + 1

    if elements:
        walk(0, 0, 0)
    return columns


def _parse_column_meta(fields: dict) -> ColumnMeta:
    return ColumnMeta(
        type=fields.get(1, PARQUET_BYTE_ARRAY),
        path_in_schema=[p.decode("utf-8", errors="replace") for p in fields.get(2, [])],
        codec=fields.get(3, UNCOMPRESSED),
        num_values=fields.get(4, 0),
        total_uncompressed_size=fields.get(5, 0),
        total_compressed_size=fields.get(6, 0),
        data_page_offset=fields.get(7, 0),
        dictionary_page_offset=fields.get(11, 0),
        encodings=fields.get(8, []),
    )


def _parse_row_group(fields: dict) -> RowGroupInfo:
    columns = []
    for col_fields in fields.get(1, []):
        meta_fields = col_fields.get(3, {})
        columns.append(ColumnChunkInfo(
            file_offset=col_fields.get(2, 0),
            meta=_parse_column_meta(meta_fields) if meta_fields else ColumnMeta(
                type=PARQUET_BYTE_ARRAY, path_in_schema=[], codec=0,
                num_values=0, total_uncompressed_size=0,
                total_compressed_size=0, data_page_offset=0,
            ),
        ))
    return RowGroupInfo(
        num_rows=fields.get(3, 0),
        total_byte_size=fields.get(2, 0),
        columns=columns,
    )


def parse_file_metadata(data: bytes) -> ParquetMetadata:
    reader = ThriftCompactReader(data)
    fields = reader.read_struct_fields()
    schema_elements = fields.get(2, [])
    row_groups_raw = fields.get(4, [])
    return ParquetMetadata(
        version=fields.get(1, 1),
        num_rows=fields.get(3, 0),
        schema=_parse_schema_elements(schema_elements),
        row_groups=[_parse_row_group(rg) for rg in row_groups_raw],
    )
