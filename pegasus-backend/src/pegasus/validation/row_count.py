# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-11T00:00:00Z
# --- END GENERATED FILE METADATA ---

"""Count physical and data rows in delimited local/GCS inputs."""

from __future__ import annotations

from typing import BinaryIO

_CHUNK_BYTES = 1024 * 1024


def count_physical_lines_stream(handle: BinaryIO, *, chunk_size: int = _CHUNK_BYTES) -> int:
    """Count newline-separated physical lines without parsing fields."""
    newline_count = 0
    nonempty = False
    ends_with_newline = True
    while True:
        block = handle.read(chunk_size)
        if not block:
            break
        if block.strip():
            nonempty = True
        newline_count += block.count(b"\n")
        ends_with_newline = block.endswith(b"\n")
    if not nonempty:
        return 0
    if ends_with_newline:
        return newline_count
    return newline_count + 1


def count_delimited_data_rows(adapter: object) -> int:
    """Return data rows after skip_rows and optional header row."""
    skip = int(getattr(adapter, "_skip_rows", 0) or 0)
    if getattr(adapter, "_has_header", True):
        skip += 1
    physical = _count_physical_lines(adapter)
    return max(0, physical - skip)


def _count_physical_lines(adapter: object) -> int:
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter

    if isinstance(adapter, FileDelimitedAdapter):
        with adapter.path.open("rb") as handle:
            return count_physical_lines_stream(handle)
    if isinstance(adapter, GcsDelimitedAdapter):
        with adapter._stream_session().open_binary(read_ahead=False) as handle:
            return count_physical_lines_stream(handle)
    getter = getattr(adapter, "get_row_count", None)
    if callable(getter):
        count = getter()
        if isinstance(count, int) and count >= 0:
            return count
    raise TypeError(f"Unsupported adapter for row counting: {type(adapter).__name__}")
