# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T22:00:00Z
# --- END GENERATED FILE METADATA ---

"""Simple CPU slot math for the FCFS validation queue (1 core reserved for OS/API)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pegasus.core.resource_tuning import physical_cpu_count

if TYPE_CHECKING:
    from pegasus.core.config import Settings


def schedulable_cpu_cores(settings: Settings, *, ncpu: int | None = None) -> int:
    """Logical CPUs workers may use (``ncpu - validation_cpu_reserve_cores``)."""
    cores = max(1, int(physical_cpu_count() if ncpu is None else ncpu))
    reserve = max(0, int(settings.validation_cpu_reserve_cores))
    return max(1, cores - reserve)


def min_cores_per_job(settings: Settings) -> int:
    return max(1, int(settings.validation_min_cpu_per_job))


def max_concurrent_by_cpu(settings: Settings, *, ncpu: int | None = None) -> int:
    """Max parallel jobs when each needs at least one schedulable core."""
    sched = schedulable_cpu_cores(settings, ncpu=ncpu)
    return max(1, sched // min_cores_per_job(settings))


def allocate_cores_per_job(settings: Settings, *, concurrent_jobs: int, ncpu: int | None = None) -> int:
    """Split schedulable CPUs evenly across *concurrent_jobs* (minimum 1 each)."""
    sched = schedulable_cpu_cores(settings, ncpu=ncpu)
    return max(1, sched // max(1, int(concurrent_jobs)))
