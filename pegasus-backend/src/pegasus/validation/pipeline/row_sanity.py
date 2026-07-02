# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-02T05:38:31Z
# --- END GENERATED FILE METADATA ---

"""Sanity checks so truncated parses cannot return as successful validation."""

from __future__ import annotations

from pegasus.validation.adapters.base import TabularSourceAdapter


def estimate_min_rows_from_bytes(file_bytes: int, *, column_count: int = 4) -> int:
    """Lower-bound row count from file size (conservative)."""
    if file_bytes <= 0:
        return 0
    avg_row = max(32, 8 * max(1, column_count))
    return max(1, file_bytes // avg_row)


def assert_reasonable_row_counts(
    source: TabularSourceAdapter,
    target: TabularSourceAdapter,
    *,
    source_rows: int,
    target_rows: int,
    compare_column_count: int,
) -> None:
    """Raise when row counts are impossibly low for on-disk file sizes."""
    src_bytes = _size_bytes(source)
    tgt_bytes = _size_bytes(target)
    cols = max(1, compare_column_count + 1)
    for label, rows, file_bytes in (
        ("source", source_rows, src_bytes),
        ("target", target_rows, tgt_bytes),
    ):
        if file_bytes is None or file_bytes < 256 * 1024:
            continue
        floor = min(100, estimate_min_rows_from_bytes(file_bytes, column_count=cols) // 20)
        if rows < floor:
            raise ValueError(
                f"{label} parsed only {rows} row(s) from {file_bytes} bytes; "
                f"expected at least ~{floor}. Check delimiter, header options, and file path."
            )


def _size_bytes(adapter: TabularSourceAdapter) -> int | None:
    getter = getattr(adapter, "get_size_bytes", None)
    if not callable(getter):
        return None
    try:
        return int(getter())
    except (OSError, ValueError):
        return None
