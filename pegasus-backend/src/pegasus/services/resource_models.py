# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T10:31:41+05:30
# --- END GENERATED FILE METADATA ---

"""Calibrated resource cost models for validation admission control."""

from __future__ import annotations

import math

# Golden footprint: 40 GiB combined CSV → ~1.48 GiB peak RSS, ~4.97 GiB workspace.
_GOLDEN_COMBINED_BYTES = 40 * 1024**3
_GOLDEN_PEAK_RSS_BYTES = 1_553_428_480
_GOLDEN_PEAK_WORKSPACE_BYTES = 5_216_277_431


def estimate_streaming_spill_disk_bytes(
    combined_bytes: int,
    *,
    min_disk_per_job_bytes: int,
) -> int:
    """Tiered spill workspace estimate (not raw CSV × multiplier)."""
    combined = max(0, int(combined_bytes))
    if combined < 1 * 1024**3:
        ratio = 1.5
    elif combined < 10 * 1024**3:
        ratio = 0.25
    elif combined < 50 * 1024**3:
        ratio = 0.15
    else:
        ratio = 0.12
    return max(min_disk_per_job_bytes, int(combined * ratio))


def estimate_streaming_job_ram_bytes(
    combined_bytes: int,
    *,
    min_ram_per_job_bytes: int,
    chunk_rows: int = 500_000,
    compare_column_count: int = 8,
) -> int:
    """Bounded RAM estimate calibrated against production profiler peaks."""
    row_bytes = max(64, min(2048, 32 * max(1, compare_column_count + 1)))
    chunk_buffers = 2
    chunk_ram = chunk_rows * row_bytes * chunk_buffers
    overhead = 384 * 1024 * 1024
    base = chunk_ram + overhead

    combined = max(0, int(combined_bytes))
    if combined >= 10 * 1024**3:
        scale = combined / _GOLDEN_COMBINED_BYTES
        conservative = int(_GOLDEN_PEAK_RSS_BYTES * max(1.0, min(2.5, scale * 1.35)))
        return max(min_ram_per_job_bytes, base, conservative)
    if combined >= 1 * 1024**3:
        return max(min_ram_per_job_bytes, base, 768 * 1024**2)
    return max(min_ram_per_job_bytes, base)


def estimate_job_ram_bytes(
    combined_bytes: int,
    *,
    ram_multiplier: float,
    min_ram_per_job_bytes: int,
    streaming: bool = False,
    chunk_rows: int = 500_000,
    compare_column_count: int = 8,
) -> int:
    if streaming or combined_bytes >= 64 * 1024 * 1024:
        return estimate_streaming_job_ram_bytes(
            combined_bytes,
            min_ram_per_job_bytes=min_ram_per_job_bytes,
            chunk_rows=chunk_rows,
            compare_column_count=compare_column_count,
        )
    return max(min_ram_per_job_bytes, int(combined_bytes * ram_multiplier))


def estimate_job_disk_bytes(
    combined_bytes: int,
    *,
    disk_headroom_multiplier: float,
    min_disk_per_job_bytes: int,
    streaming: bool = False,
) -> int:
    if streaming or combined_bytes >= 64 * 1024 * 1024:
        return estimate_streaming_spill_disk_bytes(
            combined_bytes,
            min_disk_per_job_bytes=min_disk_per_job_bytes,
        )
    return max(min_disk_per_job_bytes, int(combined_bytes * disk_headroom_multiplier))


def effective_cpu_cost_per_job(
    *,
    cpu_cores: int,
    threads_per_job: int,
    partition_reconcile_workers: int,
    combined_bytes: int = 0,
    cpu_reserve_cores: int = 1,
) -> int:
    """Cores consumed by one validation job (for parallel slot math)."""
    schedulable = max(1, cpu_cores - max(0, int(cpu_reserve_cores)))
    reconcile = max(1, partition_reconcile_workers)
    if threads_per_job > 0:
        reconcile = max(reconcile, threads_per_job)
    cost = max(1, min(schedulable, reconcile))
    # Large spill jobs use most schedulable cores (one core left for the host).
    if combined_bytes >= 10 * 1024**3:
        return schedulable
    if reconcile >= max(2, schedulable // 2):
        return schedulable
    return cost


def apply_utilization_slack(value: int, slack: float) -> int:
    """Reduce safe capacity to leave headroom (e.g. 7 of 10 slots)."""
    if value <= 1:
        return max(1, value)
    clamped = max(0.1, min(1.0, float(slack)))
    return max(1, int(math.floor(value * clamped)))
