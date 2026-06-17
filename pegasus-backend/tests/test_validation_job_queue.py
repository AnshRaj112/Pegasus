# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:03:13Z
# --- END GENERATED FILE METADATA ---

"""Tests for validation job queue concurrency."""

from __future__ import annotations

import uuid
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.services.resource_advisor import ResourceSnapshot
from pegasus.services.validation_job_queue import JobState, ValidationJobQueue


def _snapshot(*, recommended: int) -> ResourceSnapshot:
    return ResourceSnapshot(
        total_ram_bytes=16 * 1024**3,
        available_ram_bytes=8 * 1024**3,
        total_disk_bytes=100 * 1024**3,
        available_disk_bytes=50 * 1024**3,
        cpu_cores=8,
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


class _StubHandle:
    def poll(self) -> int | None:
        return None

    def failure_detail(self) -> str:
        return ""


class _StubRunner:
    def start_job(self, job_dir: Path) -> _StubHandle:
        return _StubHandle()


def test_effective_max_uses_user_cap_when_auto_tune_off() -> None:
    settings = Settings(validation_max_concurrency=2, validation_auto_tune_enabled=False)
    queue = ValidationJobQueue(settings, max_concurrency=2)
    assert queue.effective_max_concurrency() == 2


def test_effective_max_honors_user_cap_when_auto_tune_on(monkeypatch) -> None:
    settings = Settings(validation_max_concurrency=3, validation_auto_tune_enabled=True)
    queue = ValidationJobQueue(settings, max_concurrency=3)
    monkeypatch.setattr(queue, "resource_recommendation", lambda: _snapshot(recommended=8))
    assert queue.effective_max_concurrency() == 3


def test_enqueue_does_not_deadlock_under_lock(monkeypatch, tmp_path: Path) -> None:
    """Regression: resource probes must not run while self._lock is held."""
    import concurrent.futures

    settings = Settings(validation_max_concurrency=2, validation_auto_tune_enabled=False)
    queue = ValidationJobQueue(settings, max_concurrency=2)
    queue._runner = _StubRunner()  # noqa: SLF001
    monkeypatch.setattr(queue, "_stamp_resource_policy", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_write_queued_status", lambda *a, **k: None)

    real_recommendation = queue.resource_recommendation

    def tracked_recommendation():
        assert not queue._lock.locked(), "resource_recommendation must not run under queue lock"
        return real_recommendation()

    monkeypatch.setattr(queue, "resource_recommendation", tracked_recommendation)

    job_id = uuid.uuid4()
    job_dir = tmp_path / str(job_id)
    job_dir.mkdir()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        enqueue_future = pool.submit(queue.enqueue, job_id, job_dir)
        stats_future = pool.submit(lambda: queue.stats)
        enqueue_future.result(timeout=5)
        stats_future.result(timeout=5)


def test_enqueue_starts_multiple_jobs_up_to_cap(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(validation_max_concurrency=2, validation_auto_tune_enabled=False)
    queue = ValidationJobQueue(settings, max_concurrency=2)
    queue._runner = _StubRunner()  # noqa: SLF001
    monkeypatch.setattr(queue, "_stamp_resource_policy", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_write_queued_status", lambda *a, **k: None)

    jobs = []
    for _ in range(3):
        job_id = uuid.uuid4()
        job_dir = tmp_path / str(job_id)
        job_dir.mkdir()
        jobs.append(queue.enqueue(job_id, job_dir))

    assert queue.running_count == 2
    assert queue.pending_count == 1
    assert jobs[0].state == JobState.RUNNING
    assert jobs[1].state == JobState.RUNNING
    assert jobs[2].state == JobState.QUEUED
