# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T18:00:00Z
# --- END GENERATED FILE METADATA ---

"""Per-job greedy admission checks for the validation job queue."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pegasus.services.fair_cpu_scheduler import is_large_job, max_concurrent_by_cpu
from pegasus.services.job_resource_meta import estimate_job_csv_bytes, job_column_count, read_job_meta
from pegasus.services.resource_advisor import ResourceSnapshot
from pegasus.services.resource_models import estimate_job_disk_bytes, estimate_job_ram_bytes

if TYPE_CHECKING:
    from pegasus.core.config import Settings
    from pegasus.services.validation_job_queue import QueuedJob


def _job_costs(
    job_dir: object,
    *,
    settings: Settings,
    streaming: bool,
    chunk_rows: int,
    disk_headroom_multiplier: float,
    ram_multiplier: float,
    min_ram_per_job_bytes: int,
    min_disk_per_job_bytes: int,
) -> tuple[int, int]:
    path = getattr(job_dir, "job_dir", job_dir)
    meta = read_job_meta(path)
    combined = estimate_job_csv_bytes(path)
    columns = job_column_count(meta)
    ram = estimate_job_ram_bytes(
        combined,
        ram_multiplier=ram_multiplier,
        min_ram_per_job_bytes=min_ram_per_job_bytes,
        streaming=streaming,
        chunk_rows=chunk_rows,
        compare_column_count=columns,
    )
    disk = estimate_job_disk_bytes(
        combined,
        disk_headroom_multiplier=disk_headroom_multiplier,
        min_disk_per_job_bytes=min_disk_per_job_bytes,
        streaming=streaming,
    )
    return ram, disk


def _running_costs(
    running_jobs: dict[Any, QueuedJob],
    *,
    settings: Settings,
    streaming: bool,
    chunk_rows: int,
    disk_headroom_multiplier: float,
    ram_multiplier: float,
    min_ram_per_job_bytes: int,
    min_disk_per_job_bytes: int,
) -> tuple[int, int]:
    ram_total = 0
    disk_total = 0
    for job in running_jobs.values():
        ram, disk = _job_costs(
            job,
            settings=settings,
            streaming=streaming,
            chunk_rows=chunk_rows,
            disk_headroom_multiplier=disk_headroom_multiplier,
            ram_multiplier=ram_multiplier,
            min_ram_per_job_bytes=min_ram_per_job_bytes,
            min_disk_per_job_bytes=min_disk_per_job_bytes,
        )
        ram_total += ram
        disk_total += disk
    return ram_total, disk_total


def _count_large_jobs(
    jobs: dict[Any, QueuedJob] | list[QueuedJob],
    *,
    threshold_bytes: int,
) -> int:
    if isinstance(jobs, dict):
        iterable = jobs.values()
    else:
        iterable = jobs
    return sum(1 for j in iterable if is_large_job(j, threshold_bytes=threshold_bytes))


def format_mib(value: int) -> str:
    if value >= 1024**3:
        return f"{value / 1024**3:.1f} GiB"
    return f"{value / 1024**2:.0f} MiB"


def can_admit_multi(
    pending_job: QueuedJob,
    running_jobs: dict[Any, QueuedJob],
    snapshot: ResourceSnapshot,
    *,
    settings: Settings,
    effective_max: int,
    disk_headroom_multiplier: float,
    ram_multiplier: float,
    min_ram_per_job_bytes: int,
    min_disk_per_job_bytes: int,
    ram_reserve_bytes: int,
    disk_reserve_bytes: int,
    schedulable_cpu: float,
    min_cpu_per_job: float,
    large_job_threshold_bytes: int,
    streaming: bool | None = None,
    chunk_rows: int | None = None,
) -> tuple[bool, str]:
    """Return whether *pending_job* may start alongside *running_jobs*."""
    running_count = len(running_jobs)
    slot_cap = max(1, effective_max)
    cpu_cap = max_concurrent_by_cpu(settings, ncpu=snapshot.cpu_cores)
    max_parallel = max(1, min(slot_cap, cpu_cap, snapshot.max_safe_by_cpu))

    if running_count >= max_parallel:
        return False, (
            f"Queued — will start when a slot opens "
            f"({running_count}/{max_parallel} jobs running)"
        )

    prospective = running_count + 1
    if prospective * min_cpu_per_job > schedulable_cpu + 1e-6:
        return False, (
            f"Queued — will start when CPU is free "
            f"({running_count} jobs running; need {min_cpu_per_job:.1f} cores per job)"
        )

    use_streaming = streaming
    if use_streaming is None:
        use_streaming = settings.validation_gcs_streaming_only
    job_chunk_rows = chunk_rows or settings.validation_reconciliation_chunk_rows

    pending_ram, pending_disk = _job_costs(
        pending_job,
        settings=settings,
        streaming=bool(use_streaming),
        chunk_rows=job_chunk_rows,
        disk_headroom_multiplier=disk_headroom_multiplier,
        ram_multiplier=ram_multiplier,
        min_ram_per_job_bytes=min_ram_per_job_bytes,
        min_disk_per_job_bytes=min_disk_per_job_bytes,
    )
    running_ram, running_disk = _running_costs(
        running_jobs,
        settings=settings,
        streaming=bool(use_streaming),
        chunk_rows=job_chunk_rows,
        disk_headroom_multiplier=disk_headroom_multiplier,
        ram_multiplier=ram_multiplier,
        min_ram_per_job_bytes=min_ram_per_job_bytes,
        min_disk_per_job_bytes=min_disk_per_job_bytes,
    )

    available_ram = snapshot.available_ram_bytes
    available_disk = snapshot.available_disk_bytes
    ram_headroom = max(0, available_ram - ram_reserve_bytes - running_ram)
    disk_headroom = max(0, available_disk - disk_reserve_bytes - running_disk)

    if pending_ram > ram_headroom:
        return False, (
            f"Queued — will start when RAM is free (needs ~{format_mib(pending_ram)}, "
            f"{format_mib(ram_headroom)} available after {running_count} running)"
        )
    if pending_disk > disk_headroom:
        return False, (
            f"Queued — will start when disk is free (needs ~{format_mib(pending_disk)} workspace, "
            f"{format_mib(disk_headroom)} available after reservations)"
        )

    pending_large = is_large_job(pending_job, threshold_bytes=large_job_threshold_bytes)
    running_large = _count_large_jobs(running_jobs, threshold_bytes=large_job_threshold_bytes)
    if pending_large and running_large >= 1:
        combined_ram = running_ram + pending_ram
        if combined_ram > ram_headroom + running_ram:
            return False, (
                f"Queued — will start when RAM is free for another large job "
                f"({running_large} large job(s) running)"
            )
        if pending_ram > ram_headroom:
            return False, (
                "Queued — will start when RAM is free "
                f"(large job needs ~{format_mib(pending_ram)})"
            )

    return True, ""


def can_admit_job(
    pending_job: QueuedJob,
    running_jobs: dict[Any, QueuedJob],
    snapshot: ResourceSnapshot,
    *,
    settings: Settings,
    effective_max: int,
    disk_headroom_multiplier: float,
    ram_multiplier: float,
    min_ram_per_job_bytes: int,
    min_disk_per_job_bytes: int,
    ram_reserve_bytes: int,
    disk_reserve_bytes: int,
    streaming: bool | None = None,
    chunk_rows: int | None = None,
    schedulable_cpu: float | None = None,
    min_cpu_per_job: float | None = None,
    large_job_threshold_bytes: int | None = None,
) -> tuple[bool, str]:
    """Return whether a pending job may start now (False = stay queued, not rejected)."""
    from pegasus.services.fair_cpu_scheduler import schedulable_cpu_cores

    sched = (
        schedulable_cpu
        if schedulable_cpu is not None
        else schedulable_cpu_cores(settings, ncpu=snapshot.cpu_cores)
    )
    min_cpu = (
        min_cpu_per_job
        if min_cpu_per_job is not None
        else float(settings.validation_min_cpu_per_job)
    )
    large_threshold = (
        large_job_threshold_bytes
        if large_job_threshold_bytes is not None
        else int(settings.validation_large_job_subprocess_bytes)
    )
    return can_admit_multi(
        pending_job,
        running_jobs,
        snapshot,
        settings=settings,
        effective_max=effective_max,
        disk_headroom_multiplier=disk_headroom_multiplier,
        ram_multiplier=ram_multiplier,
        min_ram_per_job_bytes=min_ram_per_job_bytes,
        min_disk_per_job_bytes=min_disk_per_job_bytes,
        ram_reserve_bytes=ram_reserve_bytes,
        disk_reserve_bytes=disk_reserve_bytes,
        schedulable_cpu=sched,
        min_cpu_per_job=min_cpu,
        large_job_threshold_bytes=large_threshold,
        streaming=streaming,
        chunk_rows=chunk_rows,
    )
