# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T10:14:13Z
# --- END GENERATED FILE METADATA ---

"""Binary partition spill format — avoids JSON in hot paths."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Iterator

from pegasus.core.json_util import dumps_bytes, loads_bytes

# Outer: >I total_len
# Inner: >H key_len | key_utf8 | 8-byte fp | [>I payload_len | payload]
_KEY_LEN = struct.Struct(">H")
_PAYLOAD_LEN = struct.Struct(">I")
_COL_COUNT = struct.Struct(">H")
_COL_VALUE_LEN = struct.Struct(">H")
_FP_SIZE = 8
_FLUSH_THRESHOLD_BYTES = 256 * 1024
_COMPARE_PAYLOAD_MAGIC = b"\xcb\x01"
_COLUMNAR_MAGIC = b"CBL2"
_U32 = struct.Struct(">I")


def encode_compare_payload(ordered_columns: list[str], values: dict[str, str]) -> bytes:
    """Compact column-ordered payload (no JSON) for drilldown compare columns."""
    return encode_compare_payload_values(
        ordered_columns,
        [str(values.get(col, "")) for col in ordered_columns],
    )


def encode_compare_payload_values(ordered_columns: list[str], values: list[str]) -> bytes:
    """Encode compare values in column order without building a dict."""
    parts = [_COMPARE_PAYLOAD_MAGIC, _COL_COUNT.pack(len(ordered_columns))]
    for value in values:
        value_b = value.encode("utf-8")
        if len(value_b) > 65535:
            raise ValueError("compare column value exceeds 65535 bytes")
        parts.append(_COL_VALUE_LEN.pack(len(value_b)) + value_b)
    return b"".join(parts)


def decode_compare_payload(data: bytes, ordered_columns: list[str]) -> dict[str, str]:
    if not data.startswith(_COMPARE_PAYLOAD_MAGIC):
        decoded = loads_bytes(data)
        if isinstance(decoded, dict):
            return {str(k): str(v) for k, v in decoded.items()}
        return {}
    offset = len(_COMPARE_PAYLOAD_MAGIC)
    col_count = _COL_COUNT.unpack_from(data, offset)[0]
    offset += _COL_COUNT.size
    out: dict[str, str] = {}
    for idx in range(col_count):
        value_len = _COL_VALUE_LEN.unpack_from(data, offset)[0]
        offset += _COL_VALUE_LEN.size
        value = data[offset : offset + value_len].decode("utf-8")
        offset += value_len
        if idx < len(ordered_columns):
            out[ordered_columns[idx]] = value
    return out


def encode_columnar_partition(
    identities: list[str],
    hashes: list[int],
    *,
    col_lists: list[list[str]] | None = None,
) -> bytes:
    """Batch-encode one partition (CBL2). *col_lists* is column-major compare values."""
    n = len(identities)
    if n != len(hashes):
        raise ValueError("identity/hash length mismatch")

    buf = bytearray()
    buf.extend(_COLUMNAR_MAGIC)
    buf.extend(_U32.pack(n))

    for ident in identities:
        key_b = ident.encode("utf-8")
        if len(key_b) > 65535:
            raise ValueError("identity key exceeds 65535 bytes")
        buf.extend(_KEY_LEN.pack(len(key_b)))
        buf.extend(key_b)

    for value in hashes:
        buf.extend(int(value).to_bytes(_FP_SIZE, "big", signed=False))

    if col_lists:
        buf.extend(_COL_COUNT.pack(len(col_lists)))
        for column_values in col_lists:
            if len(column_values) != n:
                raise ValueError("column value count mismatch")
            for cell in column_values:
                value_b = str(cell).encode("utf-8")
                if len(value_b) > 65535:
                    raise ValueError("compare column value exceeds 65535 bytes")
                buf.extend(_COL_VALUE_LEN.pack(len(value_b)))
                buf.extend(value_b)

    return bytes(buf)


def encode_record(
    identity: str,
    fingerprint: bytes,
    *,
    payload: dict[str, Any] | None = None,
) -> bytes:
    key_b = identity.encode("utf-8")
    if len(key_b) > 65535:
        raise ValueError("identity key exceeds 65535 bytes")
    fp = fingerprint[:_FP_SIZE].ljust(_FP_SIZE, b"\x00")
    inner = _KEY_LEN.pack(len(key_b)) + key_b + fp
    if payload is not None:
        payload_b = payload if isinstance(payload, (bytes, bytearray)) else dumps_bytes(payload)
        inner += _PAYLOAD_LEN.pack(len(payload_b)) + payload_b
    return struct.pack(">I", len(inner)) + inner


def decode_record(
    data: bytes,
    *,
    compare_columns: list[str] | None = None,
) -> tuple[str, bytes, dict[str, Any] | None]:
    if len(data) < _KEY_LEN.size + _FP_SIZE:
        raise ValueError("truncated spill record")
    key_len = _KEY_LEN.unpack_from(data, 0)[0]
    offset = _KEY_LEN.size
    key = data[offset : offset + key_len].decode("utf-8")
    offset += key_len
    fp = data[offset : offset + _FP_SIZE]
    offset += _FP_SIZE
    payload: dict[str, Any] | None = None
    if offset < len(data):
        payload_len = _PAYLOAD_LEN.unpack_from(data, offset)[0]
        offset += _PAYLOAD_LEN.size
        payload_b = data[offset : offset + payload_len]
        if compare_columns:
            payload = decode_compare_payload(payload_b, compare_columns)
        else:
            payload = loads_bytes(payload_b)
    return key, fp, payload


class PartitionWriter:
    """Buffered append-only partition file writer."""

    __slots__ = ("base", "_handles", "_buffers", "_store_payload", "_compare_columns", "_flush_threshold")

    def __init__(
        self,
        base: Path,
        side: str,
        *,
        store_payload: bool,
        compare_columns: list[str] | None = None,
        flush_threshold: int = _FLUSH_THRESHOLD_BYTES,
    ) -> None:
        self.base = base / side
        self.base.mkdir(parents=True, exist_ok=True)
        self._handles: dict[int, Any] = {}
        self._buffers: dict[int, bytearray] = {}
        self._store_payload = store_payload
        self._compare_columns = compare_columns or []
        self._flush_threshold = flush_threshold

    def write_bytes(self, partition_id: int, data: bytes | bytearray) -> None:
        """Append pre-encoded records to a partition buffer."""
        buf = self._buffers.setdefault(partition_id, bytearray())
        buf.extend(data)
        if len(buf) >= self._flush_threshold:
            self._flush(partition_id)

    def write(
        self,
        partition_id: int,
        identity: str,
        fingerprint: bytes,
        raw: dict[str, Any],
    ) -> None:
        payload = None
        payload_b = None
        if self._store_payload:
            from pegasus.validation.pipeline.fingerprint import compare_columns_payload

            payload_b = encode_compare_payload(
                self._compare_columns,
                compare_columns_payload(raw, self._compare_columns),
            )
        record = encode_record(identity, fingerprint, payload=payload_b)
        buf = self._buffers.setdefault(partition_id, bytearray())
        buf.extend(record)
        if len(buf) >= self._flush_threshold:
            self._flush(partition_id)

    def _flush(self, partition_id: int) -> None:
        buf = self._buffers.get(partition_id)
        if not buf:
            return
        path = self.base / f"part_{partition_id:05d}.bin"
        handle = self._handles.get(partition_id)
        if handle is None:
            handle = open(path, "ab")  # noqa: SIM115
            self._handles[partition_id] = handle
        handle.write(buf)
        buf.clear()
        handle.flush()
        handle.close()
        del self._handles[partition_id]

    def close(self) -> None:
        for pid in list(self._buffers):
            self._flush(pid)
        for h in self._handles.values():
            h.close()
        self._handles.clear()
        self._buffers.clear()


def _iter_columnar_partition(
    f: Any,
    *,
    compare_columns: list[str] | None,
) -> Iterator[tuple[str, bytes, dict[str, Any] | None]]:
    row_count = _U32.unpack(f.read(4))[0]
    keys: list[str] = []
    for _ in range(row_count):
        key_len = _KEY_LEN.unpack(f.read(_KEY_LEN.size))[0]
        keys.append(f.read(key_len).decode("utf-8"))
    fingerprints = [f.read(_FP_SIZE) for _ in range(row_count)]

    payloads: list[dict[str, Any] | None] = [None] * row_count
    pos = f.tell()
    ncol_raw = f.read(_COL_COUNT.size)
    if len(ncol_raw) == _COL_COUNT.size and compare_columns:
        ncol = _COL_COUNT.unpack(ncol_raw)[0]
        if 0 < ncol <= len(compare_columns):
            col_values: list[list[str]] = []
            for _ in range(ncol):
                column: list[str] = []
                for _ in range(row_count):
                    value_len = _COL_VALUE_LEN.unpack(f.read(_COL_VALUE_LEN.size))[0]
                    column.append(f.read(value_len).decode("utf-8", errors="replace"))
                col_values.append(column)
            for i in range(row_count):
                payloads[i] = {
                    compare_columns[j]: col_values[j][i]
                    for j in range(ncol)
                }
        else:
            f.seek(pos)

    for i in range(row_count):
        yield keys[i], fingerprints[i], payloads[i]


def iter_partition(
    path: Path,
    *,
    compare_columns: list[str] | None = None,
) -> Iterator[tuple[str, bytes, dict[str, Any] | None]]:
    if not path.exists():
        return
    with open(path, "rb") as f:
        while True:
            pos = f.tell()
            magic = f.read(4)
            if len(magic) < 4:
                break
            if magic == _COLUMNAR_MAGIC:
                yield from _iter_columnar_partition(f, compare_columns=compare_columns)
                continue
            f.seek(pos)
            header = f.read(4)
            if len(header) < 4:
                break
            length = struct.unpack(">I", header)[0]
            body = f.read(length)
            if len(body) < length:
                break
            yield decode_record(body, compare_columns=compare_columns)


def list_partition_ids(work: Path, side: str) -> set[int]:
    side_dir = work / side
    if not side_dir.is_dir():
        return set()
    ids: set[int] = set()
    for path in side_dir.glob("part_*.bin"):
        try:
            ids.add(int(path.stem.split("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return ids
