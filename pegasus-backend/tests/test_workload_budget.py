# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T08:29:07Z
# --- END GENERATED FILE METADATA ---

from pegasus.core.workload_budget import plan_workload_budget


def test_plan_workload_budget_caps_workers_and_chunk_for_memory() -> None:
    budget = plan_workload_budget(
        source_bytes=20 * 1024**3,
        target_bytes=20 * 1024**3,
        compare_column_count=120,
        cpu_cores=16,
        memory_budget_bytes=10 * 1024**3,
        target_duration_seconds=15 * 60,
        requested_chunk_rows=1_000_000,
        requested_partition_buckets=256,
        requested_max_workers=16,
        requested_sub_partition_buckets=1,
    )
    assert budget.chunk_rows >= 4096
    assert budget.chunk_rows <= 1_000_000
    assert budget.max_parallel_workers <= 16
    assert budget.partition_buckets >= 8


def test_plan_workload_budget_scales_chunk_with_row_estimate() -> None:
    small = plan_workload_budget(
        source_bytes=200 * 1024**2,
        target_bytes=200 * 1024**2,
        compare_column_count=20,
        cpu_cores=8,
        memory_budget_bytes=10 * 1024**3,
        target_duration_seconds=15 * 60,
        requested_chunk_rows=500_000,
        requested_partition_buckets=64,
        requested_max_workers=8,
        requested_sub_partition_buckets=1,
        source_row_estimate=50_000,
        target_row_estimate=50_000,
    )
    large = plan_workload_budget(
        source_bytes=20 * 1024**3,
        target_bytes=20 * 1024**3,
        compare_column_count=20,
        cpu_cores=8,
        memory_budget_bytes=10 * 1024**3,
        target_duration_seconds=15 * 60,
        requested_chunk_rows=500_000,
        requested_partition_buckets=64,
        requested_max_workers=8,
        requested_sub_partition_buckets=1,
        source_row_estimate=100_000_000,
        target_row_estimate=100_000_000,
    )
    assert small.chunk_rows <= 500_000
    assert large.chunk_rows >= small.chunk_rows


def test_plan_workload_budget_auto_workers_when_zero_requested() -> None:
    budget = plan_workload_budget(
        source_bytes=10 * 1024**3,
        target_bytes=10 * 1024**3,
        compare_column_count=4,
        cpu_cores=4,
        memory_budget_bytes=12 * 1024**3,
        target_duration_seconds=180,
        requested_chunk_rows=500_000,
        requested_partition_buckets=256,
        requested_max_workers=0,
        requested_sub_partition_buckets=1,
    )
    assert budget.max_parallel_workers >= 3


def test_polars_path_never_chunks_above_cap() -> None:
    budget = plan_workload_budget(
        source_bytes=2 * 1024**3,
        target_bytes=2 * 1024**3,
        compare_column_count=11,
        cpu_cores=4,
        memory_budget_bytes=10 * 1024**3,
        target_duration_seconds=300,
        requested_chunk_rows=500_000,
        requested_partition_buckets=512,
        requested_max_workers=4,
        requested_sub_partition_buckets=1,
        source_row_estimate=10_000_000,
        target_row_estimate=10_000_000,
        inline_native_spill=False,
    )
    assert budget.chunk_rows <= 250_000

