# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T06:44:56Z
# --- END GENERATED FILE METADATA ---

"""Native ORC file reader — stripe-based streaming, pure Python."""

import struct
from pathlib import Path
from typing import Any, Iterator

from category1.readers.native.orc_format import (
    ORC_DOUBLE,
    ORC_FLOAT,
    ORC_INT,
    ORC_LONG,
    ORC_STRING,
    ORC_TYPE_NAMES,
    decode_direct_string,
    decode_orc_rle_v2_int,
    flatten_orc_schema,
)
from category1.readers.native.orc_protobuf import pb_nested, pb_uint64, read_protobuf


class NativeOrcFile:
    MAGIC = b"ORC"

    def __init__(self, path: Path):
        self.path = path
        self._footer: dict | None = None
        self._schema: list[tuple[str, int]] = []
        self._stripes: list[dict] = []

    def _read_tail(self) -> None:
        with open(self.path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size < 4:
                raise ValueError("File too small to be ORC")
            f.seek(-4, 2)
            tail = f.read(4)
            if tail[1:] != self.MAGIC:
                raise ValueError("Invalid ORC magic")
            ps_len = tail[0]
            f.seek(-(4 + ps_len), 2)
            ps_data = f.read(ps_len)
            postscript = read_protobuf(ps_data)
            footer_len = pb_uint64(postscript, 1)
            f.seek(-(4 + ps_len + footer_len), 2)
            footer_data = f.read(footer_len)
            self._footer = read_protobuf(footer_data)

        types = pb_nested(self._footer, 2)
        self._schema = flatten_orc_schema(types)
        self._stripes = pb_nested(self._footer, 3)

    def _ensure_loaded(self) -> None:
        if self._footer is None:
            self._read_tail()

    @property
    def num_rows(self) -> int:
        self._ensure_loaded()
        return pb_uint64(self._footer, 4)

    def schema_columns(self) -> list[tuple[str, str]]:
        self._ensure_loaded()
        return [(name, ORC_TYPE_NAMES.get(kind, "string")) for name, kind in self._schema if name]

    def read_stripe(self, stripe_index: int) -> list[dict[str, Any]]:
        self._ensure_loaded()
        if stripe_index >= len(self._stripes):
            return []

        stripe_info = self._stripes[stripe_index]
        offset = pb_uint64(stripe_info, 1)
        index_len = pb_uint64(stripe_info, 2)
        data_len = pb_uint64(stripe_info, 3)
        num_rows = pb_uint64(stripe_info, 5)

        with open(self.path, "rb") as f:
            f.seek(offset)
            data_section = f.read(data_len)

        col_values: list[list[Any]] = []
        pos = 0
        schema = [(n, k) for n, k in self._schema if n]

        for col_name, col_kind in schema:
            if col_kind in (ORC_INT, ORC_LONG):
                vals = []
                for _ in range(num_rows):
                    vals.append(struct.unpack("<q", data_section[pos : pos + 8])[0])
                    pos += 8
                col_values.append(vals)
            elif col_kind == ORC_STRING:
                strings = []
                for _ in range(num_rows):
                    length = struct.unpack("<i", data_section[pos : pos + 4])[0]
                    pos += 4
                    strings.append(data_section[pos : pos + length].decode("utf-8", errors="replace"))
                    pos += length
                col_values.append(strings)
            elif col_kind in (ORC_FLOAT, ORC_DOUBLE):
                fmt = "<f" if col_kind == ORC_FLOAT else "<d"
                size = 4 if col_kind == ORC_FLOAT else 8
                vals = []
                for _ in range(num_rows):
                    vals.append(struct.unpack(fmt, data_section[pos : pos + size])[0])
                    pos += size
                col_values.append(vals)
            else:
                col_values.append([None] * num_rows)

        records: list[dict[str, Any]] = []
        for i in range(num_rows):
            record = {}
            for j, (name, _) in enumerate(schema):
                vals = col_values[j]
                record[name] = vals[i] if i < len(vals) else None
            records.append(record)
        return records

    def iter_stripes(self) -> Iterator[list[dict[str, Any]]]:
        self._ensure_loaded()
        for i in range(len(self._stripes)):
            yield self.read_stripe(i)

    def num_stripes(self) -> int:
        self._ensure_loaded()
        return len(self._stripes)
