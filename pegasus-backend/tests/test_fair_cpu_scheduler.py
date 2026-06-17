# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T18:00:00Z
# --- END GENERATED FILE METADATA ---

"""Tests for fair CPU scheduler helpers."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.core.json_util import dumps_bytes
from pegasus.services.fair_cpu_scheduler import (
    allocate_cpu_shares,
    estimate_runtime_seconds,
    max_concurrent_by_cpu,
    pick_next_pending,
    priority_score,
    schedulable_cpu_cores,
)
from pegasus.services.job_resource_meta import stamp_resource_sizes
from pegasus.services.resource_advisor import ResourceSnapshot
from pegasus.services.validation_job_queue import QueuedJob


def _snapshot(*, recommended: int = 8, cpu: int = 4) -> ResourceSnapshot:
    return ResourceSnapshot(
        total_ram_bytes=16 * 1024**3,
        available_ram_bytes=12 * 1024**3,
        total_disk_bytes=100 * 1024**3,
        available_disk_bytes=50 * 1024**3,
        cpu_cores=cpu,
        swap_pressure=None,
        estimated_ram_per_job_bytes=512 * 1024**2,
        estimated_disk_per_job_bytes=2 * 1024**3,
        running_jobs_estimated_ram_bytes=0,
        max_safe_by_ram=recommended,
        max_safe_by_disk=recommended,
        max_safe_by_cpu=recommended,
        recommended_max_concurrency=recommended,
        warnings=[],
    )


def _job(tmp_path: Path, *, combined: int) -> QueuedJob:
    job_dir = tmp_path / str(uuid.uuid4())
    job_dir.mkdir()
    meta = stamp_resource_sizes(
        {},
        source_bytes=combined // 2,
        target_bytes=combined // 2,
    )
    (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))
    return QueuedJob(job_id=uuid.uuid4(), job_dir=job_dir)


def test_schedulable_cpu_respects_fraction() -> None:
    settings = Settings(validation_cpu_reserve_fraction=0.5)
    assert schedulable_cpu_cores(settings, ncpu=4) == 3.5


def test_allocate_cpu_shares_splits_evenly() -> None:
    jobs = [
        QueuedJob(job_id=uuid.uuid4(), job_dir=Path("/tmp/a")),
        QueuedJob(job_id=uuid.uuid4(), job_dir=Path("/tmp/b")),
    ]
    shares = allocate_cpu_shares(jobs, 3.5, min_cpu_per_job=0.5)
    assert len(shares) == 2
    assert abs(sum(shares.values()) - 3.5) < 1e-6
    assert all(v >= 0.5 for v in shares.values())


def test_priority_small_waiting_beats_large_low_wait(tmp_path: Path) -> None:
    settings = Settings()
    small = _job(tmp_path, combined=100 * 1024**2)
    large = _job(tmp_path, combined=40 * 1024**3)
    large.enqueued_at = time.time()
    small.enqueued_at = time.time() - 120
    small_score = priority_score(small, avg_runtime_seconds=900, settings=settings)
    large_score = priority_score(large, avg_runtime_seconds=900, settings=settings)
    assert small_score > large_score


def test_max_concurrent_by_cpu_on_four_core_host() -> None:
    settings = Settings(
        validation_min_cpu_per_job=0.5,
        validation_max_concurrent_jobs=3,
        validation_max_concurrency=10,
    )
    assert max_concurrent_by_cpu(settings, ncpu=4) == 3


def test_pick_next_prefers_high_priority_small_job(tmp_path: Path) -> None:
    settings = Settings(validation_max_concurrency=3, validation_auto_tune_enabled=False)
    small = _job(tmp_path, combined=50 * 1024**2)
    large = _job(tmp_path, combined=40 * 1024**3)
    small.enqueued_at = time.time() - 300
    large.enqueued_at = time.time()
    snapshot = _snapshot(recommended=3)
    picked, _ = pick_next_pending(
        [large, small],
        {},
        settings=settings,
        snapshot=snapshot,
        effective_max=3,
        avg_runtime_seconds=900,
        disk_headroom_multiplier=1.5,
        ram_multiplier=settings.validation_queue_ram_multiplier,
        min_ram_per_job_bytes=settings.validation_queue_min_ram_per_job_bytes,
        min_disk_per_job_bytes=settings.validation_queue_min_disk_per_job_bytes,
        ram_reserve_bytes=settings.validation_queue_ram_reserve_bytes,
        disk_reserve_bytes=settings.validation_queue_disk_reserve_bytes,
    )
    assert picked is not None
    assert picked.job_id == small.job_id


def test_estimate_runtime_scales_with_bytes(tmp_path: Path) -> None:
    settings = Settings()
    small = _job(tmp_path, combined=100 * 1024**2)
    large = _job(tmp_path, combined=40 * 1024**3)
    small_est = estimate_runtime_seconds(small, avg_runtime_seconds=900, settings=settings)
    large_est = estimate_runtime_seconds(large, avg_runtime_seconds=900, settings=settings)
    assert large_est > small_est
