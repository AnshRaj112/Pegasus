# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
# --- END GENERATED FILE METADATA ---

"""Native Parquet writer for tests and simple export — pure Python."""

import io
import struct
from typing import Any

from category1.readers.native.parquet_format import (
    PARQUET_BYTE_ARRAY,
    PARQUET_INT64,
    UNCOMPRESSED,
    PLAIN,
)
from category1.readers.native.thrift_compact import ThriftCompactReader


def _write_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _write_zigzag(value: int) -> bytes:
    return _write_varint((value << 1) ^ (value >> 63))


class ThriftCompactWriter:
    """Minimal Thrift compact writer for Parquet metadata."""

    def __init__(self):
        self.buf = io.BytesIO()
        self._last_field_id = 0

    def getvalue(self) -> bytes:
        return self.buf.getvalue()

    def write_field(self, field_id: int, field_type: int, write_fn) -> None:
        delta = field_id - self._last_field_id
        if 0 < delta <= 15:
            self.buf.write(bytes([(delta << 4) | field_type]))
        else:
            self.buf.write(bytes([field_type]))
            self.buf.write(struct.pack("<h", field_id))
        self._last_field_id = field_id
        write_fn()

    def write_i32(self, value: int) -> None:
        self.buf.write(_write_zigzag(value))

    def write_i64(self, value: int) -> None:
        self.buf.write(_write_zigzag(value))

    def write_string(self, value: bytes) -> None:
        self.buf.write(_write_varint(len(value)))
        self.buf.write(value)

    def write_list_i32(self, values: list[int]) -> None:
        self.buf.write(bytes([(len(values) << 4) | 5]))
        for v in values:
            self.write_i32(v)

    def write_struct_end(self) -> None:
        self.buf.write(b"\x00")


def _encode_plain_strings(values: list[str]) -> bytes:
    out = io.BytesIO()
    for v in values:
        encoded = v.encode("utf-8")
        out.write(struct.pack("<i", len(encoded)))
        out.write(encoded)
    return out.getvalue()


def _encode_plain_int64(values: list[int]) -> bytes:
    return b"".join(struct.pack("<q", v) for v in values)


def _make_page_header(num_values: int, uncompressed: int, compressed: int) -> bytes:
    w = ThriftCompactWriter()
    w.write_field(1, 5, lambda: w.write_i32(0))  # DATA_PAGE
    w.write_field(2, 5, lambda: w.write_i32(uncompressed))
    w.write_field(3, 5, lambda: w.write_i32(compressed))
    w.write_field(5, 5, lambda: w.write_i32(num_values))
    w.write_field(8, 5, lambda: w.write_i32(PLAIN))
    w.write_struct_end()
    return w.getvalue()


def _make_column_meta(
    name: str, physical_type: int, codec: int,
    num_values: int, data_offset: int, compressed_size: int, uncompressed_size: int,
) -> bytes:
    w = ThriftCompactWriter()
    w.write_field(1, 5, lambda: w.write_i32(physical_type))
    # path_in_schema list
    w.write_field(2, 9, lambda: (
        w.buf.write(bytes([(1 << 4) | 8])),
        w.write_string(name.encode()),
    ))
    w.write_field(3, 5, lambda: w.write_i32(codec))
    w.write_field(4, 5, lambda: w.write_i32(num_values))
    w.write_field(5, 5, lambda: w.write_i32(uncompressed_size))
    w.write_field(6, 5, lambda: w.write_i32(compressed_size))
    w.write_field(7, 5, lambda: w.write_i32(data_offset))
    w.write_field(8, 9, lambda: w.write_list_i32([PLAIN]))
    w.write_struct_end()
    return w.getvalue()


def write_parquet(path: str, columns: dict[str, list[Any]]) -> None:
    """Write a simple uncompressed Parquet file from column dict."""
    if not columns:
        raise ValueError("No columns provided")
    col_names = list(columns.keys())
    num_rows = len(next(iter(columns.values())))
    schema_cols: list[tuple[str, int, bytes]] = []

    body = io.BytesIO()
    column_metas: list[tuple[int, bytes, int]] = []

    for name in col_names:
        values = columns[name]
        if all(isinstance(v, int) for v in values):
            ptype = PARQUET_INT64
            encoded = _encode_plain_int64(values)
        else:
            ptype = PARQUET_BYTE_ARRAY
            encoded = _encode_plain_strings([str(v) for v in values])

        page_hdr = _make_page_header(num_rows, len(encoded), len(encoded))
        chunk_start = body.tell()
        body.write(page_hdr)
        body.write(encoded)
        chunk_end = body.tell()
        schema_cols.append((name, ptype, encoded))
        column_metas.append((chunk_start, name, ptype, len(encoded), chunk_end - chunk_start))

    body_bytes = body.getvalue()

    # Build file metadata
    meta_w = ThriftCompactWriter()
    meta_w.write_field(1, 5, lambda: meta_w.write_i32(1))
    # schema list
    def write_schema():
        meta_w.buf.write(bytes([(len(col_names) + 1) << 4 | 12]))
        # root
        root_w = ThriftCompactWriter()
        root_w.write_field(4, 8, lambda: root_w.write_string(b"schema"))
        root_w.write_field(5, 5, lambda: root_w.write_i32(len(col_names)))
        root_w.write_struct_end()
        meta_w.buf.write(root_w.getvalue())
        for name, ptype, _ in schema_cols:
            col_w = ThriftCompactWriter()
            col_w.write_field(1, 5, lambda p=ptype: col_w.write_i32(p))
            col_w.write_field(4, 8, lambda n=name: col_w.write_string(n.encode()))
            col_w.write_field(6, 5, lambda: col_w.write_i32(0))
            col_w.write_struct_end()
            meta_w.buf.write(col_w.getvalue())
    meta_w.write_field(2, 9, write_schema)
    meta_w.write_field(3, 6, lambda: meta_w.write_i64(num_rows))

    # row group
    def write_row_group():
        meta_w.buf.write(bytes([1 << 4 | 12]))  # list of 1 struct
        rg_w = ThriftCompactWriter()
        # columns list
        def write_columns():
            rg_w.buf.write(bytes([(len(column_metas)) << 4 | 12]))
            for chunk_start, name, ptype, enc_len, chunk_size in column_metas:
                col_w = ThriftCompactWriter()
                absolute_offset = 4 + chunk_start  # 4 = PAR1 magic size
                col_w.write_field(2, 6, lambda off=absolute_offset: col_w.write_i64(off))
                meta_bytes = _make_column_meta(
                    name, ptype, UNCOMPRESSED, num_rows,
                    0, chunk_size, enc_len,
                )
                col_w.write_field(3, 12, lambda: col_w.buf.write(meta_bytes))
                col_w.write_struct_end()
                rg_w.buf.write(col_w.getvalue())
        rg_w.write_field(1, 9, write_columns)
        rg_w.write_field(2, 6, lambda: rg_w.write_i64(len(body_bytes)))
        rg_w.write_field(3, 6, lambda: rg_w.write_i64(num_rows))
        rg_w.write_struct_end()
        meta_w.buf.write(rg_w.getvalue())
    meta_w.write_field(4, 9, write_row_group)
    meta_w.write_struct_end()
    footer = meta_w.getvalue()

    with open(path, "wb") as f:
        f.write(b"PAR1")
        f.write(body_bytes)
        f.write(footer)
        f.write(struct.pack("<I", len(footer)))
        f.write(b"PAR1")
