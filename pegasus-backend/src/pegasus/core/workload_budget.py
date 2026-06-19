# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T06:13:44Z
# --- END GENERATED FILE METADATA ---

"""Budget-aware runtime tuning for large CSV reconciliation jobs."""

from __future__ import annotations

from dataclasses import dataclass

# Polars multichar spill materializes a full chunk frame — keep chunks bounded.
_POLARS_CHUNK_CAP = 250_000


@dataclass(frozen=True)
class WorkloadBudget:
    """Resolved per-job knobs under hard memory and latency goals."""

    chunk_rows: int
    partition_buckets: int
    max_parallel_workers: int
    sub_partition_buckets: int


def _estimated_row_bytes(
    *,
    compare_column_count: int,
    identity_column_count: int,
    inline_native_spill: bool,
) -> int:
    """Conservative per-row memory footprint for spill chunk sizing."""
    columns = max(1, compare_column_count + identity_column_count)
    if inline_native_spill:
        # Rust splitter keeps only hash accumulators + one raw line buffer per chunk.
        return max(32, min(512, 8 * columns + 24))
    return max(64, min(2048, 32 * columns))


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
    identity_column_count: int = 1,
    inline_native_spill: bool = False,
) -> WorkloadBudget:
    """Return tuned spill/compare knobs that stay inside the memory budget.

    Estimates are conservative:
    - row width scales with identity + compare column count
    - inline native spill uses a much smaller live footprint than Polars frames
    - live memory ~= buffered chunks + worker overhead
    """
    cores = max(1, cpu_cores)
    file_bytes = max(1, source_bytes + target_bytes)
    columns = max(1, compare_column_count + max(1, identity_column_count))

    estimated_row_bytes = _estimated_row_bytes(
        compare_column_count=compare_column_count,
        identity_column_count=identity_column_count,
        inline_native_spill=inline_native_spill,
    )
    chunk_buffers = 1 if inline_native_spill else 2
    usable_budget = max(256 * 1024 * 1024, int(memory_budget_bytes * 0.70))
    max_rows_per_chunk = max(4096, usable_budget // (estimated_row_bytes * chunk_buffers))

    estimated_total_rows = max(1, int(source_row_estimate or 0) + int(target_row_estimate or 0))

    row_scaled_chunk = requested_chunk_rows
    if inline_native_spill:
        if estimated_total_rows <= 200_000:
            row_scaled_chunk = max(requested_chunk_rows, estimated_total_rows)
        elif estimated_total_rows >= 200_000_000:
            row_scaled_chunk = min(requested_chunk_rows * 4, max_rows_per_chunk)
        elif estimated_total_rows >= 50_000_000:
            row_scaled_chunk = min(requested_chunk_rows * 3, max_rows_per_chunk)
        elif estimated_total_rows >= 5_000_000:
            row_scaled_chunk = min(requested_chunk_rows * 2, max_rows_per_chunk)
    else:
        # Polars / PyArrow frames: never scale chunk size up with row estimates.
        row_scaled_chunk = min(requested_chunk_rows, _POLARS_CHUNK_CAP)

    chunk_rows = min(row_scaled_chunk, max_rows_per_chunk)
    chunk_rows = max(4096, chunk_rows)

    if inline_native_spill:
        # Larger chunks amortize Python spill I/O; still bounded by RAM estimate.
        inline_cap = max(250_000, usable_budget // max(1, estimated_row_bytes))
        if estimated_total_rows >= 5_000_000:
            chunk_rows = min(max(chunk_rows, 500_000), inline_cap, 2_000_000)
        elif estimated_total_rows >= 1_000_000:
            chunk_rows = min(max(chunk_rows, 250_000), inline_cap)
        else:
            chunk_rows = min(chunk_rows, inline_cap)
    else:
        chunk_rows = min(chunk_rows, _POLARS_CHUNK_CAP)

    throughput_goal_bps = file_bytes / max(1, target_duration_seconds)
    if throughput_goal_bps > 50 * 1024 * 1024 and not inline_native_spill:
        chunk_rows = max(4096, chunk_rows // 2)

    workers_cap_by_memory = max(1, usable_budget // (max(1, chunk_rows * estimated_row_bytes * chunk_buffers)))
    workers = requested_max_workers if requested_max_workers is not None else cores
    worker_ceiling = min(cores, 16 if file_bytes >= 8 * 1024**3 else 8)
    workers = min(max(1, workers), worker_ceiling, workers_cap_by_memory)

    est_rows = max(
        int(source_row_estimate or 0),
        int(target_row_estimate or 0),
        max(source_bytes, target_bytes) // estimated_row_bytes,
    )
    rows_per_partition = 5_000 if est_rows >= 50_000_000 else (10_000 if est_rows >= 5_000_000 else 2000)
    max_partitions = 512
    if file_bytes >= 20 * 1024 * 1024 * 1024:
        max_partitions = 4096
    elif file_bytes >= 10 * 1024 * 1024 * 1024:
        max_partitions = 2048
    elif file_bytes >= 1024 * 1024 * 1024:
        max_partitions = 1024
    partition_target = max(
        8,
        min(max_partitions, (int(est_rows) + rows_per_partition - 1) // rows_per_partition),
    )
    if columns >= 64:
        partition_target = min(512, int(partition_target * 1.25))
    if columns >= 500:
        partition_target = min(512, partition_target * 2)
    partitions = min(max(1, requested_partition_buckets), int(partition_target))
    sub_partitions = max(1, requested_sub_partition_buckets)

    return WorkloadBudget(
        chunk_rows=chunk_rows,
        partition_buckets=partitions,
        max_parallel_workers=workers,
        sub_partition_buckets=sub_partitions,
    )
