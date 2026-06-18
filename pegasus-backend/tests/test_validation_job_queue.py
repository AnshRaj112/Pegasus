# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T18:00:00Z
# --- END GENERATED FILE METADATA ---

"""Tests for validation job queue concurrency."""

from __future__ import annotations

import uuid
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.core.json_util import dumps_bytes
from pegasus.services.job_resource_meta import stamp_resource_sizes
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

    def force_reap(self, *, reason: str = "job finished") -> int | None:
        return None

    def set_cpu_quota(self, cpu_cores: float) -> None:
        return None


class _StubRunner:
    def start_job(self, job_dir: Path, *, allocated_cpu_cores: float | None = None) -> _StubHandle:
        return _StubHandle()

    def check_timeout(self, handle: _StubHandle, started_at: float) -> bool:
        return False


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


def test_enqueue_starts_multiple_jobs_fcfs_when_slots_allow(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        validation_max_concurrency=3,
        validation_auto_tune_enabled=False,
        validation_min_cpu_per_job=1,
        validation_cpu_reserve_cores=1,
    )
    queue = ValidationJobQueue(settings, max_concurrency=3)
    queue._runner = _StubRunner()  # noqa: SLF001
    monkeypatch.setattr(queue, "_stamp_resource_policy", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_write_queued_status", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_drain_slot_cap", lambda: (3, _snapshot(recommended=3)))

    jobs = []
    for _ in range(3):
        job_id = uuid.uuid4()
        job_dir = tmp_path / str(job_id)
        job_dir.mkdir()
        meta = stamp_resource_sizes({}, source_bytes=1024, target_bytes=1024)
        (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))
        jobs.append(queue.enqueue(job_id, job_dir))

    assert queue.running_count == 3
    assert queue.pending_count == 0
    assert all(j.state == JobState.RUNNING for j in jobs)


def test_next_job_starts_after_slot_frees(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(validation_max_concurrency=1, validation_auto_tune_enabled=False)
    queue = ValidationJobQueue(settings, max_concurrency=1)
    monkeypatch.setattr(queue, "_stamp_resource_policy", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_write_queued_status", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_drain_slot_cap", lambda: (1, _snapshot(recommended=1)))

    handles: list[_StubHandle] = []

    class _CompletingHandle(_StubHandle):
        def __init__(self) -> None:
            self._done = False

        def poll(self) -> int | None:
            return 0 if self._done else None

        def complete(self) -> None:
            self._done = True

    class _Runner:
        def start_job(self, job_dir: Path, *, allocated_cpu_cores: float | None = None) -> _CompletingHandle:
            h = _CompletingHandle()
            handles.append(h)
            return h

        def check_timeout(self, handle: _CompletingHandle, started_at: float) -> bool:
            return False

    queue._runner = _Runner()  # noqa: SLF001

    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    for job_id in (first_id, second_id):
        job_dir = tmp_path / str(job_id)
        job_dir.mkdir()
        meta = stamp_resource_sizes({}, source_bytes=1024, target_bytes=1024)
        (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))
        queue.enqueue(job_id, job_dir)

    assert queue.running_count == 1
    assert queue.pending_count == 1
    assert queue.get_job(first_id).state == JobState.RUNNING  # type: ignore[union-attr]

    handles[0].complete()
    queue._reap_finished()  # noqa: SLF001

    assert queue.running_count == 1
    assert queue.pending_count == 0
    assert queue.get_job(second_id).state == JobState.RUNNING  # type: ignore[union-attr]


def test_enqueue_many_jobs_bounded_memory(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(validation_max_concurrency=3, validation_auto_tune_enabled=False)
    queue = ValidationJobQueue(settings, max_concurrency=3)
    queue._runner = _StubRunner()  # noqa: SLF001
    monkeypatch.setattr(queue, "_stamp_resource_policy", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_write_queued_status", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_drain_slot_cap", lambda: (3, _snapshot(recommended=3)))

    for i in range(100):
        job_id = uuid.uuid4()
        job_dir = tmp_path / f"job-{i}"
        job_dir.mkdir()
        (job_dir / "meta.json").write_text("{}", encoding="utf-8")
        queue.enqueue(job_id, job_dir)

    assert queue.pending_count == 97
    assert queue.running_count == 3
    assert queue.stats["total_tracked"] == 100


def test_worker_oom_writes_failed_status(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(validation_max_concurrency=1, validation_auto_tune_enabled=False)
    queue = ValidationJobQueue(settings, max_concurrency=1)
    monkeypatch.setattr(queue, "_stamp_resource_policy", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_write_queued_status", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_drain_slot_cap", lambda: (1, _snapshot(recommended=1)))

    class _FailsLaterHandle(_StubHandle):
        def __init__(self) -> None:
            self._polls = 0

        def poll(self) -> int | None:
            self._polls += 1
            if self._polls == 1:
                return None
            return -9

        def failure_detail(self) -> str:
            return "oom"

    class _Runner:
        def start_job(self, job_dir: Path, *, allocated_cpu_cores: float | None = None) -> _FailsLaterHandle:
            return _FailsLaterHandle()

        def check_timeout(self, handle: _FailsLaterHandle, started_at: float) -> bool:
            return False

    queue._runner = _Runner()  # noqa: SLF001

    job_id = uuid.uuid4()
    job_dir = tmp_path / str(job_id)
    job_dir.mkdir()
    (job_dir / "meta.json").write_text("{}", encoding="utf-8")
    queue.enqueue(job_id, job_dir)
    queue._reap_finished()  # noqa: SLF001

    assert queue.get_job(job_id).state == JobState.FAILED  # type: ignore[union-attr]
    status = (job_dir / "status.json").read_text(encoding="utf-8")
    assert "failed" in status
    assert "out of memory" in status.lower() or "killed" in status.lower()


def test_reap_external_job_from_disk_status(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        validation_max_concurrency=1,
        validation_spawn_local_workers=False,
        validation_distributed_queue_url="redis://localhost:6379/0",
    )
    queue = ValidationJobQueue(settings, max_concurrency=1)
    monkeypatch.setattr(queue, "_stamp_resource_policy", lambda *a, **k: None)
    monkeypatch.setattr(queue, "_write_queued_status", lambda *a, **k: None)
    monkeypatch.setattr(
        "pegasus.services.distributed_validation_queue.get_distributed_queue",
        lambda _s: type("Q", (), {"enqueue": lambda *a, **k: None})(),
    )

    job_id = uuid.uuid4()
    job_dir = tmp_path / str(job_id)
    job_dir.mkdir()
    (job_dir / "meta.json").write_text("{}", encoding="utf-8")
    job = queue.enqueue(job_id, job_dir)
    assert job.external is True

    (job_dir / "status.json").write_text(
        '{"status": "completed", "phase": "completed"}',
        encoding="utf-8",
    )
    queue._reap_finished()  # noqa: SLF001
    assert queue.get_job(job_id).state == JobState.COMPLETED  # type: ignore[union-attr]
