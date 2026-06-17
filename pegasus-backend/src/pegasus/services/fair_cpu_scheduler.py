# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T18:00:00Z
# --- END GENERATED FILE METADATA ---

"""Fair CPU share allocation and priority scoring for multi-job validation."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from pegasus.core.resource_tuning import physical_cpu_count
from pegasus.services.job_resource_meta import estimate_job_csv_bytes, read_job_meta

if TYPE_CHECKING:
    from pegasus.core.config import Settings
    from pegasus.services.validation_job_queue import QueuedJob

_BASELINE_RUNTIME_SECONDS = 15 * 60
_MIN_EST_RUNTIME_SECONDS = 30.0
_REFERENCE_COMBINED_BYTES = 40 * 1024**3


def schedulable_cpu_cores(settings: Settings, *, ncpu: int | None = None) -> float:
    """Logical CPUs available for validation after OS/API reserve."""
    cores = float(physical_cpu_count() if ncpu is None else max(1, ncpu))
    fraction = float(getattr(settings, "validation_cpu_reserve_fraction", 0.5) or 0.0)
    if fraction > 0:
        return max(float(settings.validation_min_cpu_per_job), cores - fraction)
    reserve = max(0, int(settings.validation_cpu_reserve_cores))
    return max(float(settings.validation_min_cpu_per_job), cores - float(reserve))


def estimate_runtime_seconds(
    job: QueuedJob,
    *,
    avg_runtime_seconds: float,
    settings: Settings,
) -> float:
    """Estimate wall time from file size and historical average."""
    combined = estimate_job_csv_bytes(job.job_dir)
    meta = read_job_meta(job.job_dir)
    if isinstance(meta.get("combined_bytes"), int) and meta["combined_bytes"] > 0:
        combined = int(meta["combined_bytes"])
    baseline = max(_MIN_EST_RUNTIME_SECONDS, float(avg_runtime_seconds or _BASELINE_RUNTIME_SECONDS))
    if combined <= 0:
        return baseline
    scale = combined / _REFERENCE_COMBINED_BYTES
    target = float(settings.validation_target_duration_seconds or 600)
    return max(_MIN_EST_RUNTIME_SECONDS, min(baseline * max(0.05, scale), target * max(1.0, scale * 2)))


def wait_seconds(job: QueuedJob, *, now: float | None = None) -> float:
    ts = now if now is not None else time.time()
    return max(0.0, ts - job.enqueued_at)


def priority_score(
    job: QueuedJob,
    *,
    now: float | None = None,
    avg_runtime_seconds: float,
    settings: Settings,
) -> float:
    """Higher score = more urgent (anti-starvation for small / long-waiting jobs)."""
    est = estimate_runtime_seconds(job, avg_runtime_seconds=avg_runtime_seconds, settings=settings)
    wait = wait_seconds(job, now=now)
    return (wait + est) / est


def max_concurrent_by_cpu(settings: Settings, *, ncpu: int | None = None) -> int:
    schedulable = schedulable_cpu_cores(settings, ncpu=ncpu)
    min_cpu = float(settings.validation_min_cpu_per_job)
    by_cpu = max(1, int(schedulable // min_cpu))
    cap = max(1, int(settings.validation_max_concurrent_jobs or settings.validation_max_concurrency))
    return max(1, min(by_cpu, cap))


def allocate_cpu_shares(
    jobs: list[QueuedJob],
    schedulable_cpu: float,
    *,
    min_cpu_per_job: float,
) -> dict[Any, float]:
    """Split schedulable CPU evenly across running jobs (sum <= schedulable_cpu)."""
    if not jobs:
        return {}
    n = len(jobs)
    floor_total = n * min_cpu_per_job
    if floor_total > schedulable_cpu + 1e-6:
        per = schedulable_cpu / n
    else:
        per = schedulable_cpu / n
    per = max(min_cpu_per_job, per)
    return {job.job_id: per for job in jobs}


def is_large_job(job: QueuedJob, *, threshold_bytes: int) -> bool:
    combined = estimate_job_csv_bytes(job.job_dir)
    return combined >= max(1, int(threshold_bytes))


def pick_next_pending(
    pending: list[QueuedJob],
    running: dict[Any, QueuedJob],
    *,
    settings: Settings,
    snapshot: Any,
    effective_max: int,
    avg_runtime_seconds: float,
    disk_headroom_multiplier: float,
    ram_multiplier: float,
    min_ram_per_job_bytes: int,
    min_disk_per_job_bytes: int,
    ram_reserve_bytes: int,
    disk_reserve_bytes: int,
) -> tuple[QueuedJob | None, str]:
    """Return highest-priority pending job that passes admission, or (None, reason)."""
    from pegasus.services.resource_governor import can_admit_multi

    if not pending:
        return None, ""
    sched = schedulable_cpu_cores(settings)
    min_cpu = float(settings.validation_min_cpu_per_job)
    large_threshold = int(settings.validation_large_job_subprocess_bytes)

    def _score(job: QueuedJob) -> float:
        return priority_score(
            job,
            avg_runtime_seconds=avg_runtime_seconds,
            settings=settings,
        )

    ordered = sorted(pending, key=_score, reverse=True)
    best_reason = ""
    for job in ordered:
        admitted, reason = can_admit_multi(
            job,
            running,
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
        )
        if admitted:
            return job, ""
        if not best_reason and reason:
            best_reason = reason
    return None, best_reason or "Queued — waiting for CPU, RAM, or disk"
