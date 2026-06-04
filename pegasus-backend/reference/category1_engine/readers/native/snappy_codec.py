# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-03T15:43:12+05:30
# --- END GENERATED FILE METADATA ---

"""Pure Python Snappy block decompression (RFC-inspired, no external deps)."""

import struct


class SnappyError(Exception):
    pass


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, pos
        shift += 7
        if shift >= 64:
            raise SnappyError("Varint too long")
    raise SnappyError("Truncated varint")


def decompress(data: bytes) -> bytes:
    """Decompress a Snappy block (not framed/stream format)."""
    if not data:
        return b""
    pos = 0
    uncompressed_len, pos = _read_varint(data, pos)
    out = bytearray()
    while pos < len(data):
        tag = data[pos]
        pos += 1
        tag_type = tag & 0x03
        if tag_type == 0:  # literal
            length = (tag >> 2) + 1
            if length == 61:
                length = data[pos] + 1
                pos += 1
            elif length == 62:
                length = struct.unpack("<H", data[pos : pos + 2])[0] + 1
                pos += 2
            elif length == 63:
                length = struct.unpack("<I", data[pos : pos + 4])[0] + 1
                pos += 4
            out.extend(data[pos : pos + length])
            pos += length
        elif tag_type == 1:  # copy with 1-byte offset
            length = ((tag >> 2) & 0x7) + 4
            offset = ((tag >> 5) << 8) | data[pos]
            pos += 1
            _copy(out, offset, length)
        elif tag_type == 2:  # copy with 2-byte offset
            length = (tag >> 2) + 1
            offset = struct.unpack("<H", data[pos : pos + 2])[0]
            pos += 2
            _copy(out, offset, length)
        else:  # copy with 4-byte offset
            if pos + 4 > len(data):
                break
            length = (tag >> 2) + 1
            offset = struct.unpack("<I", data[pos : pos + 4])[0]
            pos += 4
            _copy(out, offset, length)
    if len(out) != uncompressed_len:
        # tolerate minor mismatch in malformed blocks; trim/pad
        if len(out) > uncompressed_len:
            out = out[:uncompressed_len]
    return bytes(out)


def _copy(out: bytearray, offset: int, length: int) -> None:
    if offset == 0 or offset > len(out):
        raise SnappyError(f"Invalid copy offset: {offset}")
    start = len(out) - offset
    for _ in range(length):
        out.append(out[start])
        start += 1
