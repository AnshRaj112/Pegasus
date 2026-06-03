"""Native ORC writer — Category-1 direct encoding profile (pure Python)."""

import struct
from typing import Any

ORC_STRUCT = 12


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


def _write_pb_field(field_num: int, wire_type: int, payload: bytes) -> bytes:
    return _write_varint((field_num << 3) | wire_type) + payload


def _write_pb_varint_field(field_num: int, value: int) -> bytes:
    return _write_pb_field(field_num, 0, _write_varint(value))


def _write_pb_bytes_field(field_num: int, data: bytes) -> bytes:
    return _write_pb_field(field_num, 2, _write_varint(len(data)) + data)


def _encode_int64_column(values: list[int]) -> bytes:
    return b"".join(struct.pack("<q", int(v)) for v in values)


def _encode_string_column(values: list[str]) -> bytes:
    out = bytearray()
    for v in values:
        encoded = v.encode("utf-8")
        out.extend(struct.pack("<i", len(encoded)))
        out.extend(encoded)
    return bytes(out)


def write_orc(path: str, columns: dict[str, list[Any]]) -> None:
    """Write an uncompressed ORC file using Category-1 direct column encoding."""
    col_names = list(columns.keys())
    num_rows = len(next(iter(columns.values())))

    column_streams: list[bytes] = []
    column_kinds: list[int] = []
    for name in col_names:
        values = columns[name]
        if all(isinstance(v, int) for v in values):
            column_kinds.append(4)  # LONG
            column_streams.append(_encode_int64_column(values))
        else:
            column_kinds.append(7)  # STRING
            column_streams.append(_encode_string_column([str(v) for v in values]))

    data_section = b"".join(column_streams)

    field_types = b""
    for name, kind in zip(col_names, column_kinds):
        ft = _write_pb_varint_field(1, kind) + _write_pb_bytes_field(2, name.encode())
        field_types += _write_pb_bytes_field(2, ft)

    root_type = _write_pb_varint_field(1, ORC_STRUCT)
    root_type += _write_pb_bytes_field(2, b"root")
    root_type += field_types

    stripe_info = (
        _write_pb_varint_field(1, 3)
        + _write_pb_varint_field(2, 0)
        + _write_pb_varint_field(3, len(data_section))
        + _write_pb_varint_field(4, 0)
        + _write_pb_varint_field(5, num_rows)
    )

    footer = (
        _write_pb_bytes_field(2, root_type)
        + _write_pb_bytes_field(3, stripe_info)
        + _write_pb_varint_field(4, num_rows)
    )
    postscript = (
        _write_pb_varint_field(1, len(footer))
        + _write_pb_varint_field(2, 0)
        + _write_pb_varint_field(3, 65536)
    )

    with open(path, "wb") as f:
        f.write(b"ORC")
        f.write(data_section)
        f.write(footer)
        f.write(postscript)
        f.write(bytes([len(postscript)]))
        f.write(b"ORC")
