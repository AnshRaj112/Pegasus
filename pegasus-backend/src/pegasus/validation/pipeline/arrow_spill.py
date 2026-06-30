# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T08:29:07Z
# --- END GENERATED FILE METADATA ---

"""Arrow IPC columnar partition spill (ARW1) — minimal decode on reconcile."""

from __future__ import annotations

import mmap
import struct
from pathlib import Path
from typing import Iterator

import polars as pl
import pyarrow as pa
import pyarrow.ipc as pa_ipc

_ARROW_MAGIC = b"ARW1"
_BLOCK_LEN = struct.Struct(">I")
_SCHEMA = pa.schema([
    ("identity", pa.string()),
    ("fingerprint", pa.uint64()),
])


def encode_arrow_partition_series(identities: pl.Series, hashes: pl.Series) -> bytes:
    """Encode from Polars series without materializing Python lists."""
    batch = pa.RecordBatch.from_arrays(
        [identities.to_arrow(), hashes.cast(pl.UInt64, strict=False).to_arrow()],
        schema=_SCHEMA,
    )
    sink = pa.BufferOutputStream()
    with pa_ipc.new_stream(sink, _SCHEMA) as writer:
        writer.write_batch(batch)
    ipc = sink.getvalue().to_pybytes()
    body = _ARROW_MAGIC + ipc
    return _BLOCK_LEN.pack(len(body)) + body


def encode_arrow_partition(identities: list[str], hashes: list[int]) -> bytes:
    """Length-prefixed Arrow IPC block: >I len | ARW1 | ipc_stream."""
    n = len(identities)
    if n != len(hashes):
        raise ValueError("identity/hash length mismatch")
    fp_array = pa.array(hashes, type=pa.uint64())
    batch = pa.RecordBatch.from_arrays(
        [
            pa.array(identities, type=pa.string()),
            fp_array,
        ],
        schema=_SCHEMA,
    )
    sink = pa.BufferOutputStream()
    with pa_ipc.new_stream(sink, _SCHEMA) as writer:
        writer.write_batch(batch)
    ipc = sink.getvalue().to_pybytes()
    body = _ARROW_MAGIC + ipc
    return _BLOCK_LEN.pack(len(body)) + body


def _iter_blocks(data: bytes | memoryview) -> Iterator[bytes]:
    offset = 0
    total = len(data)
    while offset + _BLOCK_LEN.size <= total:
        block_len = _BLOCK_LEN.unpack_from(data, offset)[0]
        offset += _BLOCK_LEN.size
        end = offset + block_len
        if end > total:
            break
        block = bytes(data[offset:end])
        offset = end
        if block[:4] == _ARROW_MAGIC:
            yield block[4:]


def iter_arrow_frames(path: Path) -> Iterator[pl.DataFrame]:
    if not path.is_file():
        return
    with open(path, "rb") as handle:
        mm = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            offset = 0
            total = len(mm)
            while offset + _BLOCK_LEN.size <= total:
                block_len = _BLOCK_LEN.unpack_from(mm, offset)[0]
                offset += _BLOCK_LEN.size
                end = offset + block_len
                if end > total:
                    break
                block = mm[offset:end]
                offset = end
                if block[:4] != _ARROW_MAGIC:
                    continue
                ipc = bytes(block[4:])
                try:
                    table = pa_ipc.open_stream(ipc).read_all()
                except Exception:
                    continue
                if table.num_rows == 0:
                    continue
                yield pl.from_arrow(table)
        finally:
            mm.close()


def read_arrow_partition(path: Path) -> pl.DataFrame | None:
    frames = list(iter_arrow_frames(path))
    if not frames:
        return None
    return pl.concat(frames, how="vertical")


def partition_has_arrow(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < _BLOCK_LEN.size + 4:
        return False
    with open(path, "rb") as f:
        header = f.read(_BLOCK_LEN.size + 4)
    if len(header) < _BLOCK_LEN.size + 4:
        return False
    block_len = _BLOCK_LEN.unpack_from(header, 0)[0]
    return header[_BLOCK_LEN.size : _BLOCK_LEN.size + 4] == _ARROW_MAGIC and block_len >= 4
