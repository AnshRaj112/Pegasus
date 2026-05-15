"""Single-pass vectorized mismatch detection for wide-column reconciliation.

Replaces the O(C × JoinCost) per-column loop with a single join materialisation
followed by **parallel** in-memory column scanning.  Complexity drops from
O(C × JoinCost) to O(JoinCost + C/W × FilterCost_on_materialized), where W is
the number of worker threads.

Memory-bounded:  processes columns in configurable chunks so the working set stays
small even with 1000+ compare columns.  Polars DataFrames are immutable and release
the GIL during C++ filter/select operations, so threading is both safe and efficient.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from .mismatch_collector import MismatchSink

logger = logging.getLogger(__name__)

# ── Tuning knobs ────────────────────────────────────────────────────────
# Columns per thread work unit.  Each chunk runs as one task in the pool.
_DEFAULT_COLUMN_CHUNK = 64

# Minimum column count before we bother spawning threads.
_PARALLEL_COLUMN_THRESHOLD = 16

# Default max worker threads for column-parallel scanning.
# Threads (not processes) because the DataFrame is already in memory
# and Polars releases the GIL during its C++ filter/select ops.
_DEFAULT_MAX_COLUMN_WORKERS = max(1, min(os.cpu_count() or 4, 8))


def _null_safe_ne(col: str, col_target: str) -> pl.Expr:
    """Return an expression that is True when the two columns differ (null-aware)."""
    return (
        pl.col(col).cast(pl.String).fill_null("__NULL__")
        != pl.col(col_target).cast(pl.String).fill_null("__NULL__")
    )


def emit_value_mismatches_single_pass(
    joined_lf: pl.LazyFrame,
    *,
    uid_column: str,
    compare_columns: list[str],
    collector: MismatchSink,
    column_chunk_size: int = _DEFAULT_COLUMN_CHUNK,
    streaming: bool = True,
    parallel_columns: bool = True,
    max_column_workers: int = _DEFAULT_MAX_COLUMN_WORKERS,
) -> None:
    """Detect value mismatches across *all* compare_columns with ONE join materialisation.

    Steps
    -----
    1. Build a **single** ``any_horizontal`` filter covering all compare columns so Polars
       only materialises rows where at least one column differs.
    2. Collect that pre-filtered join result *once* (streaming engine).
    3. Split columns into chunks and process them **in parallel** using a thread pool.
       Each worker scans its chunk of columns on the shared immutable DataFrame and
       returns a list of mismatch frames.
    4. Main thread sequentially appends worker results to the collector (thread-safe
       writes, no lock contention on the file handle).

    Parameters
    ----------
    joined_lf
        The outer-joined LazyFrame with source columns ``col`` and target columns
        ``col_target`` (produced by ``src.join(tgt, ..., suffix="_target")``).
        Must already be filtered to rows present on *both* sides.
    uid_column
        Name of the UID column on the source side of the join.
    compare_columns
        Column names to compare (source-side names; targets are ``f"{col}_target"``).
    collector
        Mismatch sink (supports ``bulk_append_from_frame`` or per-row methods).
    column_chunk_size
        Number of columns per parallel work unit.  Controls granularity of parallelism.
    streaming
        Whether to use the Polars streaming engine for the single collect.
    parallel_columns
        When True and column count exceeds ``_PARALLEL_COLUMN_THRESHOLD``, process
        column chunks concurrently using a thread pool.
    max_column_workers
        Maximum number of worker threads for column-parallel scanning.
    """
    if not compare_columns:
        return

    n_cols = len(compare_columns)
    logger.info(
        "Single-pass value mismatch detection: %d compare columns, chunk_size=%d, parallel=%s, workers=%d",
        n_cols,
        column_chunk_size,
        parallel_columns,
        max_column_workers,
    )

    # ── 1. Build horizontal any-diff filter ──────────────────────────────
    #    This ensures we only materialise rows that have *at least one* mismatch.
    #    For matching datasets the result is empty → near-zero cost.
    diff_exprs = [_null_safe_ne(c, f"{c}_target") for c in compare_columns]
    any_diff = pl.any_horizontal(diff_exprs)

    # Select only the columns we need: uid + source cols + target cols
    needed = (
        [uid_column]
        + list(compare_columns)
        + [f"{c}_target" for c in compare_columns]
    )
    # Deduplicate while preserving order (uid_column might be in compare_columns)
    seen: set[str] = set()
    select_cols: list[str] = []
    for c in needed:
        if c not in seen:
            seen.add(c)
            select_cols.append(c)

    filtered_lf = joined_lf.filter(any_diff).select(select_cols)

    # ── 2. Single collect ────────────────────────────────────────────────
    try:
        if streaming:
            mismatched_df = filtered_lf.collect(engine="streaming")
        else:
            mismatched_df = filtered_lf.collect()
    except Exception:
        logger.warning("Streaming collect failed for single-pass mismatch; falling back")
        mismatched_df = filtered_lf.collect()

    if mismatched_df.is_empty():
        logger.info("Single-pass value mismatch: no mismatched rows found")
        return

    logger.info(
        "Single-pass value mismatch: %d rows with at least one column diff (of %d columns)",
        mismatched_df.height,
        n_cols,
    )

    # ── 3. Split columns into chunks ─────────────────────────────────────
    col_chunks: list[list[str]] = [
        compare_columns[i : i + column_chunk_size]
        for i in range(0, n_cols, column_chunk_size)
    ]

    use_parallel = (
        parallel_columns
        and n_cols >= _PARALLEL_COLUMN_THRESHOLD
        and len(col_chunks) > 1
        and max_column_workers > 1
    )

    if use_parallel:
        _process_columns_parallel(
            mismatched_df,
            uid_column=uid_column,
            col_chunks=col_chunks,
            collector=collector,
            max_workers=max_column_workers,
        )
    else:
        _process_columns_sequential(
            mismatched_df,
            uid_column=uid_column,
            col_chunks=col_chunks,
            collector=collector,
        )


# ── Sequential path (small column counts or explicit opt-out) ────────────


def _process_columns_sequential(
    df: pl.DataFrame,
    *,
    uid_column: str,
    col_chunks: list[list[str]],
    collector: MismatchSink,
) -> None:
    """Process column chunks sequentially — simple path for ≤16 columns."""
    has_bulk = hasattr(collector, "bulk_append_from_frame")
    for chunk_cols in col_chunks:
        frames = _scan_column_chunk(df, uid_column=uid_column, chunk_cols=chunk_cols)
        _flush_frames_to_collector(frames, collector=collector, has_bulk=has_bulk)


# ── Parallel path (wide schemas: 16+ columns) ───────────────────────────


def _process_columns_parallel(
    df: pl.DataFrame,
    *,
    uid_column: str,
    col_chunks: list[list[str]],
    collector: MismatchSink,
    max_workers: int,
) -> None:
    """Process column chunks in parallel using a thread pool.

    Polars DataFrames are immutable and release the GIL during C++ filter/select,
    so multiple threads can safely read the same ``df`` concurrently.  Each worker
    returns its mismatch frames; the main thread flushes them to the collector
    sequentially to avoid file-handle contention.
    """
    n_workers = min(max_workers, len(col_chunks))
    has_bulk = hasattr(collector, "bulk_append_from_frame")

    logger.info(
        "Parallel column processing: %d chunks across %d threads",
        len(col_chunks),
        n_workers,
    )

    with ThreadPoolExecutor(max_workers=n_workers, thread_name_prefix="col_cmp") as pool:
        # Submit all column chunks to the pool
        future_to_idx = {
            pool.submit(
                _scan_column_chunk,
                df,
                uid_column=uid_column,
                chunk_cols=chunk,
            ): idx
            for idx, chunk in enumerate(col_chunks)
        }

        # Collect results in submission order to keep output deterministic
        results: dict[int, list[pl.DataFrame]] = {}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception:
                logger.exception("Column chunk %d failed", idx)
                results[idx] = []

    # Flush to collector in original order (deterministic output)
    for idx in sorted(results.keys()):
        _flush_frames_to_collector(results[idx], collector=collector, has_bulk=has_bulk)

    total_mismatch_frames = sum(len(v) for v in results.values())
    logger.info(
        "Parallel column processing complete: %d mismatch frames from %d chunks",
        total_mismatch_frames,
        len(col_chunks),
    )


# ── Shared helpers (used by both sequential and parallel paths) ──────────


def _scan_column_chunk(
    df: pl.DataFrame,
    *,
    uid_column: str,
    chunk_cols: list[str],
) -> list[pl.DataFrame]:
    """Scan a chunk of columns on an already-materialised DataFrame.

    Returns a list of mismatch frames (one per column that has differences).
    This function is **pure** — no side effects, safe to call from any thread.
    """
    frames: list[pl.DataFrame] = []
    for col in chunk_cols:
        tgt_col = f"{col}_target"
        if tgt_col not in df.columns:
            continue

        # Fast in-memory boolean mask — no disk I/O, no join re-execution
        mask = _null_safe_ne(col, tgt_col)
        diff = df.filter(mask)
        if diff.is_empty():
            continue

        result = diff.select([
            pl.col(uid_column).cast(pl.String).alias("uid"),
            pl.lit("value_mismatch").alias("mismatch_type"),
            pl.lit(col).alias("column_name"),
            pl.col(col).cast(pl.String).alias("source_value"),
            pl.col(tgt_col).cast(pl.String).alias("target_value"),
            pl.lit("{}", dtype=pl.String).alias("row_detail"),
        ])
        frames.append(result)

    return frames


def _flush_frames_to_collector(
    frames: list[pl.DataFrame],
    *,
    collector: MismatchSink,
    has_bulk: bool,
) -> None:
    """Write mismatch frames to the collector (always called from the main thread)."""
    for result in frames:
        if result.is_empty():
            continue
        if has_bulk:
            collector.bulk_append_from_frame(result)
        else:
            for rec in result.to_dicts():
                collector.add_value_mismatch(
                    uid=str(rec["uid"]),
                    column_name=str(rec["column_name"]),
                    source_value=rec["source_value"],
                    target_value=rec["target_value"],
                    source_record={},
                    target_record={},
                )
