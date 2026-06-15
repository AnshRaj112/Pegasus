# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T09:02:38Z
# --- END GENERATED FILE METADATA ---

"""Minimal Protocol Buffers wire-format reader for ORC metadata."""

from typing import Any


def read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, pos
        shift += 7
    raise EOFError("Truncated protobuf varint")


def read_protobuf(data: bytes) -> dict[int, list[Any]]:
    """Parse protobuf wire format into field_number -> list of values."""
    fields: dict[int, list[Any]] = {}
    pos = 0
    while pos < len(data):
        tag, pos = read_varint(data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07
        if wire_type == 0:
            val, pos = read_varint(data, pos)
        elif wire_type == 1:
            val = data[pos : pos + 8]
            pos += 8
        elif wire_type == 2:
            length, pos = read_varint(data, pos)
            val = data[pos : pos + length]
            pos += length
        elif wire_type == 5:
            val = data[pos : pos + 4]
            pos += 4
        else:
            break
        fields.setdefault(field_num, []).append(val)
    return fields


def pb_uint64(fields: dict, key: int, idx: int = 0) -> int:
    vals = fields.get(key, [])
    if not vals:
        return 0
    if isinstance(vals[idx], int):
        return vals[idx]
    val, _ = read_varint(vals[idx], 0)
    return val


def pb_bytes(fields: dict, key: int, idx: int = 0) -> bytes:
    vals = fields.get(key, [])
    return vals[idx] if vals else b""


def pb_nested(fields: dict, key: int) -> list[dict[int, list[Any]]]:
    return [read_protobuf(b) for b in fields.get(key, []) if isinstance(b, bytes)]
