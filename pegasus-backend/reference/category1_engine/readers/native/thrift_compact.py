# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T07:31:26Z
# --- END GENERATED FILE METADATA ---

"""Minimal Apache Thrift Compact Protocol reader for Parquet metadata."""

import struct
from typing import Any


class ThriftCompactReader:
    """Reads Thrift compact-encoded structs used in Parquet footers and page headers."""

    TYPES = {
        0: "stop",
        1: "true",
        2: "false",
        3: "byte",
        4: "i16",
        5: "i32",
        6: "i64",
        7: "double",
        8: "binary",
        9: "list",
        10: "set",
        11: "map",
        12: "struct",
    }

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self._last_field = (0, 0)  # (field_id, type)

    def _read(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError("Unexpected end of Thrift data")
        chunk = self.data[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def read_byte(self) -> int:
        return self._read(1)[0]

    def read_varint(self) -> int:
        result = 0
        shift = 0
        while True:
            b = self.read_byte()
            result |= (b & 0x7F) << shift
            if (b & 0x80) == 0:
                return result
            shift += 7
            if shift >= 64:
                raise ValueError("Varint overflow")

    def read_zigzag(self) -> int:
        u = self.read_varint()
        return (u >> 1) ^ -(u & 1)

    def read_i32(self) -> int:
        return self.read_zigzag()

    def read_i64(self) -> int:
        return self.read_zigzag()

    def read_double(self) -> float:
        return struct.unpack("<d", self._read(8))[0]

    def read_string(self) -> bytes:
        length = self.read_varint()
        return self._read(length)

    def read_field_header(self) -> tuple[int, int]:
        byte = self.read_byte()
        if byte == 0:
            return 0, 0
        type_nibble = byte & 0x0F
        delta = (byte >> 4) & 0x0F
        if delta == 0:
            field_id = self.read_i16_raw()
        else:
            field_id = self._last_field[0] + delta
        self._last_field = (field_id, type_nibble)
        return field_id, type_nibble

    def read_i16_raw(self) -> int:
        return struct.unpack("<h", self._read(2))[0]

    def read_list_header(self) -> tuple[int, int]:
        size_type = self.read_byte()
        size = size_type >> 4
        elem_type = size_type & 0x0F
        if size == 15:
            size = self.read_varint()
        return size, elem_type

    def skip(self, field_type: int) -> None:
        if field_type == 0:
            return
        if field_type in (1, 2):
            return
        if field_type == 3:
            self._read(1)
        elif field_type == 4:
            self._read(2)
        elif field_type in (5, 8):
            self.read_varint()
        elif field_type == 6:
            self.read_varint()
        elif field_type == 7:
            self._read(8)
        elif field_type in (9, 10):
            size, elem_type = self.read_list_header()
            for _ in range(size):
                self.skip(elem_type)
        elif field_type == 11:
            _, _, kv_type = self.read_map_header()
            k_type, v_type = kv_type
            size, _ = self.read_map_header_size()
            for _ in range(size):
                self.skip(k_type)
                self.skip(v_type)
        elif field_type == 12:
            self.skip_struct()

    def read_map_header(self) -> tuple[int, int, tuple[int, int]]:
        size = self.read_byte()
        kv = self.read_byte()
        k_type = kv >> 4
        v_type = kv & 0x0F
        if size == 15:
            size = self.read_varint()
        return size, k_type, (k_type, v_type)

    def read_map_header_size(self) -> tuple[int, tuple[int, int]]:
        size = self.read_byte()
        kv = self.read_byte()
        k_type = kv >> 4
        v_type = kv & 0x0F
        if size == 15:
            size = self.read_varint()
        return size, (k_type, v_type)

    def skip_struct(self) -> None:
        self._last_field = (0, 0)
        while True:
            field_id, field_type = self.read_field_header()
            if field_type == 0:
                break
            self.skip(field_type)

    def read_struct_fields(self) -> dict[int, Any]:
        self._last_field = (0, 0)
        fields: dict[int, Any] = {}
        while True:
            field_id, field_type = self.read_field_header()
            if field_type == 0:
                break
            fields[field_id] = self.read_value(field_type)
        return fields

    def read_value(self, field_type: int) -> Any:
        if field_type == 1:
            return True
        if field_type == 2:
            return False
        if field_type == 3:
            return self.read_byte()
        if field_type == 4:
            return self.read_i16_raw()
        if field_type == 5:
            return self.read_i32()
        if field_type == 6:
            return self.read_i64()
        if field_type == 7:
            return self.read_double()
        if field_type == 8:
            return self.read_string()
        if field_type in (9, 10):
            saved = self._last_field
            result = self.read_list(field_type)
            self._last_field = saved
            return result
        if field_type == 11:
            saved = self._last_field
            result = self.read_map()
            self._last_field = saved
            return result
        if field_type == 12:
            saved = self._last_field
            result = self.read_struct_fields()
            self._last_field = saved
            return result
        raise ValueError(f"Unsupported Thrift type: {field_type}")

    def read_list(self, field_type: int = 9) -> list[Any]:
        size, elem_type = self.read_list_header()
        return [self.read_value(elem_type) for _ in range(size)]

    def read_map(self) -> dict[Any, Any]:
        size, k_type, (kt, vt) = self.read_map_header()
        result = {}
        for _ in range(size):
            k = self.read_value(kt)
            v = self.read_value(vt)
            result[k] = v
        return result
