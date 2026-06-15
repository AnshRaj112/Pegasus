# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:10:14Z
# --- END GENERATED FILE METADATA ---

"""Parquet page and column value decoders — pure Python."""

import gzip
import struct
from typing import Any

from category1.readers.native import snappy_codec
from category1.readers.native.parquet_format import (
    BIT_PACKED,
    DATA_PAGE,
    DATA_PAGE_V2,
    DICTIONARY_PAGE,
    GZIP,
    PARQUET_BOOLEAN,
    PARQUET_BYTE_ARRAY,
    PARQUET_DOUBLE,
    PARQUET_FIXED_LEN_BYTE_ARRAY,
    PARQUET_FLOAT,
    PARQUET_INT32,
    PARQUET_INT64,
    PARQUET_INT96,
    PLAIN,
    PLAIN_DICTIONARY,
    RLE,
    RLE_DICTIONARY,
    SNAPPY,
    UNCOMPRESSED,
    SchemaColumn,
)
from category1.readers.native.thrift_compact import ThriftCompactReader


def decompress_page(data: bytes, codec: int) -> bytes:
    if codec == UNCOMPRESSED:
        return data
    if codec == SNAPPY:
        return snappy_codec.decompress(data)
    if codec == GZIP:
        return gzip.decompress(data)
    raise NotImplementedError(f"Unsupported Parquet compression codec: {codec}")


def parse_page_header(data: bytes) -> tuple[dict, int]:
    reader = ThriftCompactReader(data)
    fields = reader.read_struct_fields()
    return fields, reader.pos


def _read_unsigned_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            return result, pos
        shift += 7
    raise EOFError("Truncated RLE varint")


def decode_rle_bitpacked_hybrid(data: bytes, bit_width: int, num_values: int) -> list[int]:
    """Decode Parquet RLE/bit-packed hybrid encoding for levels and indices."""
    if not data:
        return [0] * num_values
    pos = 0
    values: list[int] = []
    while pos < len(data) and len(values) < num_values:
        indicator, pos = _read_unsigned_varint(data, pos)
        if indicator & 1 == 0:
            # RLE run
            run_length = indicator >> 1
            if pos >= len(data):
                break
            val, pos = _read_unsigned_varint(data, pos)
            values.extend([val] * run_length)
        else:
            # Bit-packed run
            num_groups = indicator >> 1
            bytes_needed = num_groups * bit_width
            packed = data[pos : pos + ((bytes_needed + 7) // 8)]
            pos += (bytes_needed + 7) // 8
            mask = (1 << bit_width) - 1
            bit_pos = 0
            for _ in range(num_groups * 8):
                if len(values) >= num_values:
                    break
                byte_idx = bit_pos // 8
                bit_offset = bit_pos % 8
                if byte_idx >= len(packed):
                    break
                val = (packed[byte_idx] >> bit_offset) & mask
                if bit_offset + bit_width > 8 and byte_idx + 1 < len(packed):
                    bits_from_next = bit_width - (8 - bit_offset)
                    val |= (packed[byte_idx + 1] & ((1 << bits_from_next) - 1)) << (8 - bit_offset)
                values.append(val)
                bit_pos += bit_width
    return values[:num_values]


def _bit_width_for_max(max_level: int) -> int:
    if max_level <= 0:
        return 0
    width = 0
    while (1 << width) <= max_level:
        width += 1
    return width


def decode_plain_values(data: bytes, col: SchemaColumn, count: int) -> list[Any]:
    pos = 0
    values: list[Any] = []
    ptype = col.physical_type
    for _ in range(count):
        if ptype == PARQUET_BOOLEAN:
            values.append(bool(data[pos]))
            pos += 1
        elif ptype == PARQUET_INT32:
            values.append(struct.unpack("<i", data[pos : pos + 4])[0])
            pos += 4
        elif ptype == PARQUET_INT64:
            values.append(struct.unpack("<q", data[pos : pos + 8])[0])
            pos += 8
        elif ptype == PARQUET_FLOAT:
            values.append(struct.unpack("<f", data[pos : pos + 4])[0])
            pos += 4
        elif ptype == PARQUET_DOUBLE:
            values.append(struct.unpack("<d", data[pos : pos + 8])[0])
            pos += 8
        elif ptype == PARQUET_BYTE_ARRAY:
            length = struct.unpack("<i", data[pos : pos + 4])[0]
            pos += 4
            values.append(data[pos : pos + length].decode("utf-8", errors="replace"))
            pos += length
        elif ptype == PARQUET_FIXED_LEN_BYTE_ARRAY:
            values.append(data[pos : pos + col.type_length])
            pos += col.type_length
        elif ptype == PARQUET_INT96:
            values.append(data[pos : pos + 12])
            pos += 12
        else:
            raise NotImplementedError(f"Unsupported physical type: {ptype}")
    return values


def decode_dictionary_page(data: bytes, col: SchemaColumn) -> list[Any]:
    if not data:
        return []
    # Dictionary page: PLAIN-encoded values for entire dictionary
    count = struct.unpack("<i", data[:4])[0] if len(data) >= 4 else 0
    if count <= 0:
        # Some writers omit count prefix; decode until end
        return decode_plain_values(data, col, _estimate_dict_size(data, col))
    return decode_plain_values(data[4:], col, count)


def _estimate_dict_size(data: bytes, col: SchemaColumn) -> int:
    pos = 0
    count = 0
    while pos < len(data):
        if col.physical_type == PARQUET_BYTE_ARRAY:
            if pos + 4 > len(data):
                break
            length = struct.unpack("<i", data[pos : pos + 4])[0]
            pos += 4 + length
        elif col.physical_type == PARQUET_INT64:
            pos += 8
        elif col.physical_type == PARQUET_INT32:
            pos += 4
        else:
            break
        count += 1
    return max(count, 1)


class ColumnPageDecoder:
    """Decodes all pages in a column chunk into a flat list of values."""

    def __init__(self, col: SchemaColumn):
        self.col = col
        self.dictionary: list[Any] | None = None

    def decode_chunk(self, chunk_data: bytes, codec: int) -> list[Any]:
        raw = decompress_page(chunk_data, codec)
        pos = 0
        all_values: list[Any] = []

        while pos < len(raw):
            header_fields, header_end = parse_page_header(raw[pos:])
            pos += header_end
            page_type = header_fields.get(1, DATA_PAGE)
            uncompressed_size = header_fields.get(2, 0)
            compressed_size = header_fields.get(3, 0)

            if compressed_size > 0:
                page_body = raw[pos : pos + compressed_size]
                pos += compressed_size
            elif uncompressed_size > 0:
                page_body = raw[pos : pos + uncompressed_size]
                pos += uncompressed_size
            else:
                page_body = raw[pos:]
                pos = len(raw)

            if page_type == DICTIONARY_PAGE:
                self.dictionary = decode_dictionary_page(page_body, self.col)
                continue

            if page_type in (DATA_PAGE, DATA_PAGE_V2):
                values = self._decode_data_page(page_body, header_fields, page_type)
                all_values.extend(values)

        return all_values

    def _decode_data_page(
        self, body: bytes, header: dict, page_type: int
    ) -> list[Any]:
        col = self.col
        num_values = header.get(5, 0) or header.get(4, 0)

        if page_type == DATA_PAGE_V2:
            return self._decode_data_page_v2(body, header)

        pos = 0
        def_levels: list[int] = []
        rep_levels: list[int] = []

        if col.max_repetition_level > 0:
            rl_bw = _bit_width_for_max(col.max_repetition_level)
            rl_len = struct.unpack("<i", body[pos : pos + 4])[0]
            pos += 4
            rep_levels = decode_rle_bitpacked_hybrid(body[pos : pos + rl_len], rl_bw, num_values)
            pos += rl_len

        if col.max_definition_level > 0:
            dl_bw = _bit_width_for_max(col.max_definition_level)
            if pos + 4 > len(body):
                dl_len = 0
            else:
                dl_len = struct.unpack("<i", body[pos : pos + 4])[0]
                pos += 4
            if dl_len > 0:
                def_levels = decode_rle_bitpacked_hybrid(body[pos : pos + dl_len], dl_bw, num_values)
                pos += dl_len

        encoding = header.get(8, PLAIN)
        value_data = body[pos:]

        if encoding in (PLAIN_DICTIONARY, RLE_DICTIONARY) and self.dictionary is not None:
            idx_bw = struct.unpack("<B", value_data[:1])[0] if value_data else 0
            indices = decode_rle_bitpacked_hybrid(value_data[1:], idx_bw, num_values)
            raw_values = [self.dictionary[i] if i < len(self.dictionary) else None for i in indices]
        elif encoding == RLE and col.physical_type == PARQUET_BOOLEAN:
            bw = 1
            raw_values = decode_rle_bitpacked_hybrid(value_data, bw, num_values)
            raw_values = [bool(v) for v in raw_values]
        elif encoding == PLAIN:
            non_null = num_values
            if def_levels:
                non_null = sum(1 for d in def_levels if d == col.max_definition_level)
            raw_values = decode_plain_values(value_data, col, non_null)
            if def_levels:
                raw_values = _apply_definition_levels(raw_values, def_levels, col.max_definition_level)
        else:
            raise NotImplementedError(f"Unsupported encoding: {encoding}")

        return raw_values[:num_values] if num_values else raw_values

    def _decode_data_page_v2(self, body: bytes, header: dict) -> list[Any]:
        col = self.col
        num_values = header.get(4, 0)
        pos = 0
        # V2 header fields embedded in page
        if len(body) < 4:
            return []
        pos += 4  # num_values nullable
        pos += 1  # encoding
        def_len = struct.unpack("<i", body[pos : pos + 4])[0]
        pos += 4
        def_levels = decode_rle_bitpacked_hybrid(
            body[pos : pos + def_len], _bit_width_for_max(col.max_definition_level), num_values
        ) if def_len > 0 and col.max_definition_level > 0 else []
        pos += def_len
        rep_len = struct.unpack("<i", body[pos : pos + 4])[0]
        pos += 4 + rep_len

        encoding = header.get(8, PLAIN)
        value_data = body[pos:]

        if encoding in (PLAIN_DICTIONARY, RLE_DICTIONARY) and self.dictionary:
            idx_bw = struct.unpack("<B", value_data[:1])[0] if value_data else 0
            indices = decode_rle_bitpacked_hybrid(value_data[1:], idx_bw, num_values)
            return [self.dictionary[i] if i < len(self.dictionary) else None for i in indices]

        non_null = sum(1 for d in def_levels if d == col.max_definition_level) if def_levels else num_values
        raw_values = decode_plain_values(value_data, col, non_null)
        if def_levels:
            raw_values = _apply_definition_levels(raw_values, def_levels, col.max_definition_level)
        return raw_values


def _apply_definition_levels(
    values: list[Any], def_levels: list[int], max_def: int
) -> list[Any]:
    result: list[Any] = []
    val_idx = 0
    for dl in def_levels:
        if dl == max_def:
            result.append(values[val_idx] if val_idx < len(values) else None)
            val_idx += 1
        else:
            result.append(None)
    return result
