# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T14:52:27Z
# --- END GENERATED FILE METADATA ---

"""Rust-backed multichar splitter with inline hash → partition spill."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO

try:
    import pegasus_native as _native

    _AVAILABLE = bool(_native.extension_available())
except ImportError:
    _native = None  # type: ignore[assignment]
    _AVAILABLE = False

SpillChunk = dict[str, Any]
SpillResult = dict[str, Any]


def native_extension_available() -> bool:
    return _AVAILABLE


def spill_mmap_file(
    path: Path,
    output_dir: Path,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
    chunk_rows: int,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    track_merkle: bool = False,
    drilldown_path: str | None = None,
) -> SpillResult:
    if not _AVAILABLE or _native is None:
        raise RuntimeError("pegasus_native extension is not installed")
    return _native.spill_mmap_file(
        str(path),
        str(output_dir),
        delimiter,
        has_header,
        skip_rows,
        chunk_rows,
        identity_columns,
        compare_columns,
        num_partitions,
        track_merkle,
        drilldown_path,
    )


def spill_stream_file(
    source: BinaryIO,
    output_dir: Path,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
    chunk_rows: int,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    track_merkle: bool = False,
    block_size: int = 16 * 1024 * 1024,
    drilldown_path: str | None = None,
) -> SpillResult:
    if not _AVAILABLE or _native is None:
        raise RuntimeError("pegasus_native extension is not installed")
    return _native.spill_stream_file(
        source.read,
        str(output_dir),
        delimiter,
        has_header,
        skip_rows,
        chunk_rows,
        identity_columns,
        compare_columns,
        num_partitions,
        track_merkle,
        block_size,
        drilldown_path,
    )


def iter_mmap_spill_chunks(
    path: Path,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
    chunk_rows: int,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
) -> Iterator[SpillChunk]:
    if not _AVAILABLE or _native is None:
        raise RuntimeError("pegasus_native extension is not installed")
    yield from _native.iter_mmap_spill_chunks(
        str(path),
        delimiter,
        has_header,
        skip_rows,
        chunk_rows,
        identity_columns,
        compare_columns,
        num_partitions,
    )


def iter_stream_spill_chunks(
    source: BinaryIO,
    *,
    delimiter: str,
    has_header: bool,
    skip_rows: int,
    chunk_rows: int,
    identity_columns: list[str],
    compare_columns: list[str],
    num_partitions: int,
    block_size: int = 16 * 1024 * 1024,
) -> Iterator[SpillChunk]:
    if not _AVAILABLE or _native is None:
        raise RuntimeError("pegasus_native extension is not installed")
    yield from _native.iter_stream_spill_chunks(
        source.read,
        delimiter,
        has_header,
        skip_rows,
        chunk_rows,
        identity_columns,
        compare_columns,
        num_partitions,
        block_size,
    )
