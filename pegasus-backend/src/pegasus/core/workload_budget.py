# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-02T14:24:09+05:30
# --- END GENERATED FILE METADATA ---

"""Budget-aware runtime tuning for large CSV reconciliation jobs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadBudget:
    """Resolved per-job knobs under hard memory and latency goals."""

    chunk_rows: int
    partition_buckets: int
    max_parallel_workers: int
    sub_partition_buckets: int


def plan_workload_budget(
    *,
    source_bytes: int,
    target_bytes: int,
    compare_column_count: int,
    cpu_cores: int,
    memory_budget_bytes: int,
    target_duration_seconds: int,
    requested_chunk_rows: int,
    requested_partition_buckets: int,
    requested_max_workers: int | None,
    requested_sub_partition_buckets: int,
    source_row_estimate: int | None = None,
    target_row_estimate: int | None = None,
) -> WorkloadBudget:
    """Return tuned spill/compare knobs that stay inside the memory budget.

    The estimates are conservative and intentionally simple:
    - row width guess: 32 bytes per compared field + UID overhead
    - live memory ~= 2 buffered chunks + worker overhead
    """
    cores = max(1, cpu_cores)
    file_bytes = max(1, source_bytes + target_bytes)
    columns = max(1, compare_column_count + 1)

    # Coarse row width estimate suitable for CSV of mixed numeric/text values.
    estimated_row_bytes = max(64, min(2048, 32 * columns))
    # Keep 30% for interpreter, allocator fragmentation, and OS page cache churn.
    usable_budget = max(256 * 1024 * 1024, int(memory_budget_bytes * 0.70))
    max_rows_per_chunk = max(4096, usable_budget // (estimated_row_bytes * 2))

    estimated_total_rows = max(1, int(source_row_estimate or 0) + int(target_row_estimate or 0))

    # Row-aware baseline: small files fit into one/few chunks, huge files use larger chunks.
    row_scaled_chunk = requested_chunk_rows
    if estimated_total_rows <= 200_000:
        row_scaled_chunk = max(requested_chunk_rows, estimated_total_rows)
    elif estimated_total_rows >= 200_000_000:
        row_scaled_chunk = requested_chunk_rows * 3
    elif estimated_total_rows >= 50_000_000:
        row_scaled_chunk = requested_chunk_rows * 2

    chunk_rows = min(row_scaled_chunk, max_rows_per_chunk)
    chunk_rows = max(4096, chunk_rows)

    # If the target is tight for very large files, reduce chunk size to shorten latency spikes.
    throughput_goal_bps = file_bytes / max(1, target_duration_seconds)
    if throughput_goal_bps > 50 * 1024 * 1024:
        chunk_rows = max(4096, chunk_rows // 2)

    workers_cap_by_memory = max(1, usable_budget // (max(1, chunk_rows * estimated_row_bytes * 2)))
    workers = requested_max_workers if requested_max_workers is not None else cores
    workers = min(max(1, workers), cores, workers_cap_by_memory)

    # More partitions for wider rows/files, but clamp to requested ceiling.
    partition_target = max(8, min(1024, file_bytes // (512 * 1024 * 1024)))
    if columns >= 500:
        partition_target *= 2
    partitions = min(max(1, requested_partition_buckets), max(8, int(partition_target)))
    sub_partitions = max(1, requested_sub_partition_buckets)

    return WorkloadBudget(
        chunk_rows=chunk_rows,
        partition_buckets=partitions,
        max_parallel_workers=workers,
        sub_partition_buckets=sub_partitions,
    )
