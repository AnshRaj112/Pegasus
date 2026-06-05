# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
# --- END GENERATED FILE METADATA ---

"""ORC format constants and stream decoders."""

import struct
from typing import Any

from category1.readers.native.orc_protobuf import pb_bytes, pb_nested, pb_uint64, read_protobuf, read_varint

# ORC TypeKind
ORC_BOOLEAN = 0
ORC_BYTE = 1
ORC_SHORT = 2
ORC_INT = 3
ORC_LONG = 4
ORC_FLOAT = 5
ORC_DOUBLE = 6
ORC_STRING = 7
ORC_CHAR = 8
ORC_VARCHAR = 9

ORC_TYPE_NAMES = {
    ORC_BOOLEAN: "boolean",
    ORC_BYTE: "int8",
    ORC_SHORT: "int16",
    ORC_INT: "int32",
    ORC_LONG: "int64",
    ORC_FLOAT: "float",
    ORC_DOUBLE: "double",
    ORC_STRING: "string",
    ORC_CHAR: "string",
    ORC_VARCHAR: "string",
}

# Compression
ORC_COMPRESS_NONE = 0


def parse_orc_type(type_pb: dict) -> tuple[str, int]:
    kind = pb_uint64(type_pb, 1)
    name = pb_bytes(type_pb, 2).decode("utf-8", errors="replace")
    return name, kind


def decode_orc_rle_v2_int(data: bytes, num_values: int, is_signed: bool = True) -> tuple[list[int], int]:
    """Decode ORC RLE v2 integer stream; returns (values, bytes_consumed)."""
    if not data:
        return [0] * num_values, 0
    pos = 0
    start = 0
    values: list[int] = []
    while pos < len(data) and len(values) < num_values:
        first, pos = read_varint(data, pos)
        if first < 0x80:
            repeat = (first >> 3) + 3
            delta = first & 0x07
            if delta > 3:
                delta -= 8
            base = values[-1] + delta if values else 0
            values.extend([base] * repeat)
        elif first < 0x100:
            run_len = ((first - 0x80) >> 1) + 1 if first >= 0x80 else (first >> 1) + 1
            if first >= 0x80:
                run_len = ((first - 0x80) >> 1) + 1
            else:
                run_len = (first >> 1) + 1
            for _ in range(run_len):
                if len(values) >= num_values:
                    break
                if is_signed:
                    v, pos = read_varint(data, pos)
                    v = (v >> 1) ^ -(v & 1)
                else:
                    v, pos = read_varint(data, pos)
                values.append(v)
        else:
            v, pos = read_varint(data, pos)
            v = (v >> 1) ^ -(v & 1) if is_signed else v
            values.append(v)
    return values[:num_values], pos - start


def decode_direct_string(data: bytes, length_data: bytes, num_values: int) -> list[str]:
    lengths, _ = decode_orc_rle_v2_int(length_data, num_values, is_signed=False)
    strings: list[str] = []
    pos = 0
    for length in lengths:
        if length == 0:
            strings.append("")
        else:
            strings.append(data[pos : pos + length].decode("utf-8", errors="replace"))
            pos += length
    return strings


def flatten_orc_schema(types: list[dict]) -> list[tuple[str, int]]:
    """Return leaf columns (name, kind) from ORC type tree."""
    if not types:
        return []
    root = types[0]
    root_kind = pb_uint64(root, 1)
    subtypes = pb_nested(root, 2)

    # STRUCT (12) or root with children
    if subtypes and root_kind in (12, 0):
        columns: list[tuple[str, int]] = []
        for st in subtypes:
            name, kind = parse_orc_type(st)
            nested = pb_nested(st, 2)
            if nested and kind == 12:
                for child in nested:
                    columns.append(parse_orc_type(child))
            elif name:
                columns.append((name, kind))
        return columns

    name, kind = parse_orc_type(root)
    return [(name, kind)] if name else [("col_0", kind)]
