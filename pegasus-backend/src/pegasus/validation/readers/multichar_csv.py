# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T09:01:26Z
# --- END GENERATED FILE METADATA ---

"""Fast multi-byte delimiter CSV load (no quotes) for generated / simple flat files."""

from __future__ import annotations

import mmap
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

import polars as pl

_BLOCK_BYTES = 16 * 1024 * 1024


def sample_has_quotes_bytes(data: bytes, *, max_bytes: int = 65536) -> bool:
    chunk = data[:max_bytes]
    return b'"' in chunk or b"'" in chunk


def sample_has_quotes(path: Path, *, max_bytes: int = 65536) -> bool:
    with path.open("rb") as handle:
        return sample_has_quotes_bytes(handle.read(max_bytes))


def can_use_fast_multichar_load_bytes(data: bytes, delimiter: str) -> bool:
    """True when *delimiter* is multi-byte UTF-8 and the prefix has no quoted fields."""
    if not delimiter or len(delimiter) < 2:
        return False
    try:
        delim_b = delimiter.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if not delim_b:
        return False
    return not sample_has_quotes_bytes(data)


def can_use_fast_multichar_load(path: Path, delimiter: str) -> bool:
    """True when *delimiter* is multi-byte UTF-8 and the file prefix has no quoted fields."""
    with path.open("rb") as handle:
        return can_use_fast_multichar_load_bytes(handle.read(65536), delimiter)


def _encode_delimiter(delimiter: str) -> bytes:
    return delimiter.encode("utf-8")


def _parse_line_batch(
    lines: list[bytes],
    *,
    delim_b: bytes,
    headers: list[str],
) -> pl.DataFrame:
    col_count = len(headers)
    fields_batch = [line.rstrip(b"\r").split(delim_b) for line in lines]
    columns: dict[str, list[str | None]] = {
        headers[i]: [
            fields[i].decode("utf-8", errors="replace") if i < len(fields) else None
            for fields in fields_batch
        ]
        for i in range(col_count)
    }
    return pl.DataFrame(columns)


def _iter_multichar_mmap_batches(
    path: Path,
    *,
    delim_b: bytes,
    has_header: bool,
    skip_rows: int,
    chunk_rows: int,
) -> Iterator[pl.DataFrame]:
    """Memory-map large local files and yield fixed-size row batches."""
    with path.open("rb") as handle:
        mm = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
    try:
        headers: list[str] | None = None
        skipped = 0
        pending = bytearray()
        line_buf: list[bytes] = []

        def _emit() -> pl.DataFrame | None:
            nonlocal line_buf
            if not line_buf or headers is None:
                return None
            frame = _parse_line_batch(line_buf, delim_b=delim_b, headers=headers)
            line_buf = []
            return frame

        offset = 0
        size = mm.size()
        while offset < size:
            end = min(size, offset + _BLOCK_BYTES)
            pending.extend(mm[offset:end])
            offset = end
            while True:
                nl = pending.find(b"\n")
                if nl < 0:
                    break
                line = bytes(pending[:nl])
                del pending[: nl + 1]
                if not line:
                    continue
                if headers is None:
                    if skipped < skip_rows:
                        skipped += 1
                        continue
                    if has_header:
                        headers = [
                            cell.decode("utf-8", errors="replace")
                            for cell in line.rstrip(b"\r").split(delim_b)
                        ]
                        continue
                    first_fields = line.rstrip(b"\r").split(delim_b)
                    col_count = max(1, len(first_fields))
                    headers = [f"col_{i}" for i in range(col_count)]
                    line_buf.append(line)
                    continue
                line_buf.append(line)
                if len(line_buf) >= chunk_rows:
                    frame = _emit()
                    if frame is not None:
                        yield frame
        if pending:
            stripped = bytes(pending).rstrip(b"\r\n")
            if stripped:
                if headers is None:
                    if skipped >= skip_rows:
                        if has_header:
                            headers = [
                                cell.decode("utf-8", errors="replace")
                                for cell in stripped.split(delim_b)
                            ]
                        else:
                            first_fields = stripped.split(delim_b)
                            headers = [f"col_{i}" for i in range(max(1, len(first_fields)))]
                            line_buf.append(stripped)
                elif headers is not None:
                    line_buf.append(stripped)
        frame = _emit()
        if frame is not None:
            yield frame
    finally:
        mm.close()


def _iter_multichar_stream_batches(
    source: BinaryIO,
    *,
    delim_b: bytes,
    has_header: bool,
    skip_rows: int,
    chunk_rows: int,
) -> Iterator[pl.DataFrame]:
    """Buffered binary stream reader for GCS / non-seekable inputs."""
    headers: list[str] | None = None
    skipped = 0
    pending = bytearray()
    line_buf: list[bytes] = []

    def _emit() -> pl.DataFrame | None:
        nonlocal line_buf
        if not line_buf or headers is None:
            return None
        frame = _parse_line_batch(line_buf, delim_b=delim_b, headers=headers)
        line_buf = []
        return frame

    while True:
        block = source.read(_BLOCK_BYTES)
        if block:
            pending.extend(block)
        while True:
            nl = pending.find(b"\n")
            if nl < 0:
                break
            line = bytes(pending[:nl])
            del pending[: nl + 1]
            if not line:
                continue
            if headers is None:
                if skipped < skip_rows:
                    skipped += 1
                    continue
                if has_header:
                    headers = [
                        cell.decode("utf-8", errors="replace")
                        for cell in line.rstrip(b"\r").split(delim_b)
                    ]
                    continue
                first_fields = line.rstrip(b"\r").split(delim_b)
                col_count = max(1, len(first_fields))
                headers = [f"col_{i}" for i in range(col_count)]
                line_buf.append(line)
                continue
            line_buf.append(line)
            if len(line_buf) >= chunk_rows:
                frame = _emit()
                if frame is not None:
                    yield frame
        if not block:
            if pending:
                stripped = bytes(pending).rstrip(b"\r\n")
                pending.clear()
                if stripped:
                    if headers is None and skipped >= skip_rows:
                        if has_header:
                            headers = [
                                cell.decode("utf-8", errors="replace")
                                for cell in stripped.split(delim_b)
                            ]
                        else:
                            first_fields = stripped.split(delim_b)
                            headers = [f"col_{i}" for i in range(max(1, len(first_fields)))]
                            line_buf.append(stripped)
                    elif headers is not None:
                        line_buf.append(stripped)
            frame = _emit()
            if frame is not None:
                yield frame
            break


def iter_multichar_csv_batches(
    source: Path | BinaryIO,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
    chunk_rows: int,
) -> Iterator[pl.DataFrame]:
    """Yield bounded Polars frames from a multi-byte delimiter file (no full read)."""
    delim_b = _encode_delimiter(delimiter)
    if isinstance(source, Path):
        yield from _iter_multichar_mmap_batches(
            source,
            delim_b=delim_b,
            has_header=has_header,
            skip_rows=skip_rows,
            chunk_rows=chunk_rows,
        )
        return
    yield from _iter_multichar_stream_batches(
        source,
        delim_b=delim_b,
        has_header=has_header,
        skip_rows=skip_rows,
        chunk_rows=chunk_rows,
    )


def load_multichar_csv_fast(
    source: Path | BinaryIO,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
) -> pl.DataFrame:
    """Parse delimiter-separated text with ``bytes.split`` (no RFC 4180 quotes)."""
    if isinstance(source, Path):
        frames = list(
            iter_multichar_csv_batches(
                source,
                delimiter=delimiter,
                has_header=has_header,
                skip_rows=skip_rows,
                chunk_rows=500_000,
            )
        )
        if not frames:
            return pl.DataFrame()
        return pl.concat(frames, how="vertical")

    delim_b = _encode_delimiter(delimiter)
    data = source.read()
    lines = data.split(b"\n")
    start = skip_rows
    if has_header and start < len(lines):
        header_line = lines[start].rstrip(b"\r")
        start += 1
        if not header_line:
            return pl.DataFrame()
        headers = [cell.decode("utf-8", errors="replace") for cell in header_line.split(delim_b)]
    else:
        headers = []

    col_count = len(headers)
    if col_count == 0:
        return pl.DataFrame()

    body = [line for line in lines[start:] if line.rstrip(b"\r")]
    return _parse_line_batch(body, delim_b=delim_b, headers=headers)
