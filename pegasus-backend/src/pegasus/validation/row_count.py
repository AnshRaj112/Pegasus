# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-28T11:55:42Z
# --- END GENERATED FILE METADATA ---

"""Count physical and data rows in delimited local/GCS inputs."""

from __future__ import annotations

from typing import BinaryIO

_CHUNK_BYTES = 1024 * 1024
_PROFILE_PREFIX_BYTES = 512 * 1024
_PROFILE_EXACT_MAX_BYTES = 8 * 1024 * 1024


def count_physical_lines_in_block(block: bytes) -> int:
    """Count physical lines in an in-memory byte block (same rules as stream)."""
    if not block.strip():
        return 0
    newline_count = block.count(b"\n")
    if block.endswith(b"\n"):
        return newline_count
    return newline_count + 1


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


def _delimited_skip_rows(adapter: object) -> int:
    skip = int(getattr(adapter, "_skip_rows", 0) or 0)
    if getattr(adapter, "_has_header", True):
        skip += 1
    return skip


def count_delimited_data_rows(adapter: object) -> int:
    """Return data rows after skip_rows and optional header row."""
    skip = _delimited_skip_rows(adapter)
    physical = _count_physical_lines(adapter)
    return max(0, physical - skip)


def _read_profile_prefix(adapter: object) -> bytes:
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter

    if isinstance(adapter, GcsDelimitedAdapter):
        return adapter._load_sample_prefix()
    if isinstance(adapter, FileDelimitedAdapter):
        size = adapter.path.stat().st_size
        with adapter.path.open("rb") as handle:
            return handle.read(min(_PROFILE_PREFIX_BYTES, size))
    raise TypeError(f"Unsupported adapter for row estimation: {type(adapter).__name__}")


def _fallback_row_estimate(adapter: object, *, size: int, skip: int) -> int:
    try:
        column_count = len(adapter.get_schema().columns)
    except Exception:
        column_count = 8
    from pegasus.validation.pipeline.pipeline import _estimate_row_count_from_bytes

    return max(0, _estimate_row_count_from_bytes(size, column_count=column_count) - skip)


def estimate_delimited_data_rows(adapter: object) -> int:
    """Estimate data rows from object size and a bounded prefix sample."""
    skip = _delimited_skip_rows(adapter)
    getter = getattr(adapter, "get_size_bytes", None)
    size = int(getter()) if callable(getter) else 0
    if size <= 0:
        return 0

    prefix = _read_profile_prefix(adapter)
    physical_in_prefix = count_physical_lines_in_block(prefix)
    if physical_in_prefix <= 0:
        return _fallback_row_estimate(adapter, size=size, skip=skip)

    sampled_bytes = len(prefix)
    complete_lines = physical_in_prefix
    if not prefix.endswith(b"\n"):
        last_nl = prefix.rfind(b"\n")
        if last_nl >= 0:
            sampled_bytes = last_nl + 1
            complete_lines -= 1
    if complete_lines <= 0 or sampled_bytes <= 0:
        return _fallback_row_estimate(adapter, size=size, skip=skip)

    avg_line_bytes = sampled_bytes / complete_lines
    total_physical = round(size / avg_line_bytes)
    return max(0, total_physical - skip)


def profile_delimited_data_rows(adapter: object) -> int:
    """Fast row count for cloud profile UI (exact only for small local files)."""
    from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
    from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter

    if isinstance(adapter, GcsDelimitedAdapter):
        return estimate_delimited_data_rows(adapter)
    if isinstance(adapter, FileDelimitedAdapter):
        if adapter.path.stat().st_size <= _PROFILE_EXACT_MAX_BYTES:
            return count_delimited_data_rows(adapter)
        return estimate_delimited_data_rows(adapter)
    return count_delimited_data_rows(adapter)


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
