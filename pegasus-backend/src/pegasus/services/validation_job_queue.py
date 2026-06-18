# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Concurrency-limited FCFS validation job queue."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pegasus.core.config import Settings
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.services.queue_cpu import allocate_cores_per_job, schedulable_cpu_cores
from pegasus.services.cpu_quota import update_cpu_limit
from pegasus.services.resource_governor import can_admit_job
from pegasus.services.background_validation_runner import (
    BackgroundValidationRunner,
    ValidationJobHandle,
)
from pegasus.services.queue_resource_policy import QueueResourcePolicy
from pegasus.services.resource_advisor import (
    ResourceSnapshot,
    compute_resource_recommendation,
)
from pegasus.services.host_memory import available_worker_memory_bytes
from pegasus.services.job_resource_meta import job_column_count, read_job_meta
from pegasus.services.queue_recovery import collect_orphaned_queued_job_dirs, recover_orphaned_jobs
from pegasus.validation.job_workspace import release_job_workspace

logger = logging.getLogger(__name__)

_ACTIVE_JOB_CAP = 2000


def _failure_message(rc: int | None, detail: str) -> str:
    if rc in (-9, 137):
        tail = detail.strip()
        base = "Worker killed (likely out of memory)"
        return f"{base}: {tail}" if tail else base
    if rc == -15:
        return "Worker terminated (SIGTERM)"
    tail = detail.strip()
    if tail:
        return f"Validation worker exited with code {rc}: {tail[-2000:]}"
    return f"Validation worker exited with code {rc}"


def _read_disk_job_status(job_dir: Path) -> str | None:
    status_path = job_dir / "status.json"
    if not status_path.is_file():
        return None
    try:
        st = loads_str(status_path.read_text(encoding="utf-8"))
        if isinstance(st, dict):
            return str(st.get("status") or "").lower() or None
    except (OSError, ValueError, TypeError):
        pass
    return None


class JobState(StrEnum):
    """Lifecycle states for a queued validation job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueuedJob:
    """In-memory representation of a queued validation job."""

    job_id: uuid.UUID
    job_dir: Path
    enqueued_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    state: JobState = JobState.QUEUED
    handle: ValidationJobHandle | None = None
    external: bool = False
    position: int = 0  # 0-based queue position when queued
    allocated_cpu_cores: float | None = None


class ValidationJobQueue:
    """FCFS queue for validation jobs with CPU/RAM admission control."""

    def __init__(
        self,
        settings: Settings,
        *,
        max_concurrency: int | None = None,
    ) -> None:
        mc = max_concurrency if max_concurrency is not None else settings.validation_max_concurrency
        self._max_concurrency: int = max(1, int(mc))
        self._settings = settings
        self._runner = BackgroundValidationRunner(settings)
        self._auto_tune_enabled: bool = settings.validation_auto_tune_enabled
        self._resource_policy: QueueResourcePolicy = QueueResourcePolicy.from_settings(settings)

        # Ordered queue of pending jobs (FIFO)
        self._pending: deque[QueuedJob] = deque()
        # Currently running jobs keyed by job_id
        self._running: dict[uuid.UUID, QueuedJob] = {}
        # Active jobs only (pending + running + recent finished); status.json is durable.
        self._finished: dict[uuid.UUID, QueuedJob] = {}
        self._active_jobs: dict[uuid.UUID, QueuedJob] = {}
        # Last resource snapshot (cached for stats endpoint)
        self._last_resource_snapshot: ResourceSnapshot | None = None

        self._lock = threading.Lock()
        self._drain_event = asyncio.Event()
        self._drain_task: asyncio.Task[None] | None = None
        self._stopped = False
        self._avg_runtime_seconds: float = 15 * 60

        logger.info(
            "ValidationJobQueue created max_concurrency=%d auto_tune=%s external_workers=%s "
            "threads_per_job=%d disk_mult=%.2f mem_budget_mib=%.1f",
            self._max_concurrency,
            self._auto_tune_enabled,
            self._uses_external_workers(),
            self._resource_policy.threads_per_job,
            self._resource_policy.disk_headroom_multiplier,
            self._resource_policy.memory_budget_bytes / (1024**2),
        )

    def _uses_external_workers(self) -> bool:
        url = (self._settings.validation_distributed_queue_url or "").strip()
        if not url:
            return False
        if self._settings.validation_spawn_local_workers:
            logger.warning(
                "validation_spawn_local_workers=true prevents dispatch to validation-worker; "
                "large jobs may OOM the API process. Set PEGASUS_VALIDATION_SPAWN_LOCAL_WORKERS=false."
            )
            return False
        return True

    def _safe_to_spawn_local_worker(self, job: QueuedJob) -> tuple[bool, str]:
        """Block large jobs from starting inside a small API/container cgroup."""
        from pegasus.services.host_memory import cgroup_memory_limit_bytes, worker_memory_budget_bytes
        from pegasus.services.job_resource_meta import estimate_job_csv_bytes

        threshold = int(self._settings.validation_large_job_subprocess_bytes)
        combined = estimate_job_csv_bytes(job.job_dir)
        if combined < max(1, threshold):
            return True, ""
        cgroup = cgroup_memory_limit_bytes()
        budget = worker_memory_budget_bytes(self._settings)
        cap = budget or cgroup or 0
        if cap > 0 and cap < 6 * 1024**3:
            return False, (
                "Queued — large job must run in validation-worker "
                "(set PEGASUS_VALIDATION_SPAWN_LOCAL_WORKERS=false and Redis worker URL)"
            )
        return True, ""

    def recover_from_disk(self) -> None:
        """On API startup: fail stale running jobs and re-enqueue orphaned queued jobs."""
        _requeued, failed = recover_orphaned_jobs(self._settings)
        if failed:
            logger.warning("Recovery marked %d stale running jobs as failed", failed)
        orphans = collect_orphaned_queued_job_dirs(self._settings)
        for job_id, job_dir in orphans:
            with self._lock:
                if job_id in self._active_jobs or job_id in self._running:
                    continue
            self.enqueue(job_id, job_dir)
        if orphans:
            logger.info("Re-enqueued %d orphaned queued jobs from disk", len(orphans))

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def running_count(self) -> int:
        with self._lock:
            return len(self._running)

    @staticmethod
    def cpu_cores_available() -> int:
        """Number of logical CPU cores on the host."""
        return max(1, os.cpu_count() or 1)

    def schedulable_cpu_cores_available(self) -> int:
        """CPUs workers may use (one core reserved for OS/API by default)."""
        return schedulable_cpu_cores(self._settings, ncpu=self.cpu_cores_available())

    def set_max_concurrency(self, value: int) -> int:
        """Update the concurrency cap at runtime.  Returns the clamped value actually set.

        The new limit takes effect immediately.  Running jobs are never killed.
        """
        clamped = max(1, int(value))
        with self._lock:
            old = self._max_concurrency
            self._max_concurrency = clamped
        logger.info("max_concurrency changed %d → %d", old, clamped)
        self._try_start_pending()
        self._drain_event.set()
        return clamped

    def set_auto_tune(self, enabled: bool) -> None:
        """Enable or disable automatic resource-based concurrency adjustment."""
        self._auto_tune_enabled = enabled
        logger.info("auto_tune_enabled set to %s", enabled)

    @property
    def resource_policy(self) -> QueueResourcePolicy:
        return self._resource_policy

    def set_threads_per_job(self, value: int) -> int:
        """Set worker thread cap per job (0 = auto). Returns clamped value."""
        cores = self.cpu_cores_available()
        clamped = max(0, min(int(value), cores))
        policy = self._resource_policy.clamp(cpu_cores=cores)
        self._resource_policy = QueueResourcePolicy(
            threads_per_job=clamped,
            disk_headroom_multiplier=policy.disk_headroom_multiplier,
            memory_budget_bytes=policy.memory_budget_bytes,
            target_duration_seconds=policy.target_duration_seconds,
        )
        logger.info("threads_per_job set to %d (effective=%d)", clamped, self.effective_threads_per_job())
        self._drain_event.set()
        return clamped

    def set_disk_headroom_multiplier(self, value: float) -> float:
        """Set per-job disk headroom multiplier. Returns clamped value."""
        cores = self.cpu_cores_available()
        clamped = max(1.0, min(10.0, float(value)))
        policy = self._resource_policy.clamp(cpu_cores=cores)
        self._resource_policy = QueueResourcePolicy(
            threads_per_job=policy.threads_per_job,
            disk_headroom_multiplier=clamped,
            memory_budget_bytes=policy.memory_budget_bytes,
            target_duration_seconds=policy.target_duration_seconds,
        )
        logger.info("disk_headroom_multiplier set to %.2f", clamped)
        self._drain_event.set()
        return clamped

    def effective_threads_per_job(self) -> int:
        return self._resource_policy.effective_threads(cpu_cores=self.cpu_cores_available())

    def resource_recommendation(self) -> ResourceSnapshot:
        """Compute a fresh resource snapshot and recommendation."""
        workspace = None
        temp_dir = self._settings.validation_reconciliation_temp_dir
        if temp_dir:
            workspace = Path(temp_dir)

        with self._lock:
            running = dict(self._running)
            pending = list(self._pending)

        policy = self._resource_policy
        snapshot = compute_resource_recommendation(
            running_jobs=running,
            pending_jobs=pending,
            settings=self._settings,
            workspace_path=workspace,
            disk_headroom_multiplier=policy.disk_headroom_multiplier,
            threads_per_job=policy.threads_per_job,
        )
        self._last_resource_snapshot = snapshot
        return snapshot

    def effective_max_concurrency(self, *, snapshot: ResourceSnapshot | None = None) -> int:
        """Parallel slot cap used by the drain loop (resource-aware only when auto-tune is on)."""
        if self._auto_tune_enabled:
            try:
                snap = snapshot or self.resource_recommendation()
                recommended = max(1, snap.recommended_max_concurrency)
                return max(1, min(self._max_concurrency, recommended))
            except Exception:
                logger.warning("Resource advisor failed, using user-set max_concurrency", exc_info=True)
        return max(1, self._max_concurrency)

    def _drain_slot_cap(self) -> tuple[int, ResourceSnapshot | None]:
        """Effective parallel slots for enqueue/drain (skips resource probes when auto-tune is off)."""
        if self._auto_tune_enabled:
            snapshot = self.resource_recommendation()
            return self.effective_max_concurrency(snapshot=snapshot), snapshot
        return max(1, self._max_concurrency), None

    @property
    def stats(self) -> dict[str, Any]:
        """Snapshot of queue statistics."""
        with self._lock:
            policy = self._resource_policy
            result = {
                "max_concurrency": self._max_concurrency,
                "cpu_cores_available": self.cpu_cores_available(),
                "auto_tune_enabled": self._auto_tune_enabled,
                "threads_per_job": policy.threads_per_job,
                "disk_headroom_multiplier": policy.disk_headroom_multiplier,
                "memory_budget_bytes": policy.memory_budget_bytes,
                "target_duration_seconds": policy.target_duration_seconds,
                "effective_threads_per_job": self.effective_threads_per_job(),
                "pending": len(self._pending),
                "running": len(self._running),
                "finished": len(self._finished),
                "total_tracked": len(self._active_jobs) + len(self._finished),
            }
        if self._auto_tune_enabled:
            snapshot = self.resource_recommendation()
            result["effective_max_concurrency"] = self.effective_max_concurrency(snapshot=snapshot)
            result["utilization_slack"] = self._settings.validation_utilization_slack
            result["resource_advisor"] = snapshot.to_dict()
        else:
            result["effective_max_concurrency"] = max(1, self._max_concurrency)
            result["utilization_slack"] = self._settings.validation_utilization_slack
            result["resource_advisor"] = {}
        return result

    def enqueue(self, job_id: uuid.UUID, job_dir: Path) -> QueuedJob:
        """Add a job to the queue.  Returns the :class:`QueuedJob` immediately."""
        with self._lock:
            existing = self._active_jobs.get(job_id)
            if existing is not None and existing.state in (JobState.QUEUED, JobState.RUNNING):
                return existing
        job = QueuedJob(job_id=job_id, job_dir=job_dir.resolve())
        effective, _snapshot = self._drain_slot_cap()
        with self._lock:
            job.position = len(self._pending)
            self._pending.append(job)
            self._active_jobs[job_id] = job
            self._update_queue_positions()
            self._refresh_pending_statuses_locked(effective_max=effective)
            logger.info(
                "Job %s enqueued position=%d pending=%d running=%d effective_cap=%d user_cap=%d",
                job_id,
                job.position,
                len(self._pending),
                len(self._running),
                effective,
                self._max_concurrency,
            )

        # Start immediately when capacity allows (do not wait for the drain-loop tick).
        self._try_start_pending()
        with self._lock:
            if job.state == JobState.QUEUED:
                self._write_queued_status(job)
        self._drain_event.set()
        return job

    def get_job(self, job_id: uuid.UUID) -> QueuedJob | None:
        """Return the in-memory job record when active; None if only on disk."""
        with self._lock:
            hit = self._active_jobs.get(job_id)
            if hit is not None:
                return hit
            return self._finished.get(job_id)

    def get_queue_position(self, job_id: uuid.UUID) -> int | None:
        """0-based position in the pending queue, or None if not queued."""
        with self._lock:
            for i, job in enumerate(self._pending):
                if job.job_id == job_id:
                    return i
            return None

    def list_jobs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return a snapshot of active/recent jobs (most recent first)."""
        with self._lock:
            jobs = sorted(
                {**self._active_jobs, **self._finished}.values(),
                key=lambda j: j.enqueued_at,
                reverse=True,
            )
            running_jobs = len(self._running)
        effective_max = self.effective_max_concurrency()
        return [
            {
                "job_id": str(j.job_id),
                "state": j.state.value,
                "enqueued_at": j.enqueued_at,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
                "position": j.position if j.state == JobState.QUEUED else None,
                "estimated_wait_seconds": (
                    self._estimate_wait_seconds_for_position(
                        queue_position=j.position,
                        effective_max=effective_max,
                        running_jobs=running_jobs,
                    )
                    if j.state == JobState.QUEUED
                    else None
                ),
                "estimated_start_epoch_s": (
                    time.time()
                    + self._estimate_wait_seconds_for_position(
                        queue_position=j.position,
                        effective_max=effective_max,
                        running_jobs=running_jobs,
                    )
                    if j.state == JobState.QUEUED
                    else None
                ),
                "queue_wait_reason": self._read_queue_reason(j) if j.state == JobState.QUEUED else None,
            }
            for j in jobs[:limit]
        ]

    # ── Drain loop ────────────────────────────────────────────────

    def start_drain_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Launch the background task that promotes pending → running."""
        if self._drain_task is not None:
            return
        _loop = loop or asyncio.get_event_loop()
        self._drain_task = _loop.create_task(self._drain_loop(), name="validation-queue-drain")
        logger.info("Validation job queue drain loop started")

    async def _drain_loop(self) -> None:
        """Continuously promote queued jobs when concurrency slots are available."""
        while not self._stopped:
            self._drain_event.clear()
            self._try_start_pending()
            self._reap_finished()

            # Re-check at least every 2 seconds (handles subprocess completion)
            try:
                await asyncio.wait_for(self._drain_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass

    def _try_start_pending(self) -> None:
        """Start FCFS head jobs while CPU, RAM, and disk slots are available."""
        effective_max, snapshot = self._drain_slot_cap()
        if snapshot is None:
            snapshot = self.resource_recommendation()

        policy = self._resource_policy
        ncpu = self.cpu_cores_available()

        while True:
            with self._lock:
                if not self._pending:
                    return
                if len(self._running) >= effective_max:
                    return
                head = self._pending[0]
                running_copy = dict(self._running)

            admitted, reason = can_admit_job(
                head,
                running_copy,
                snapshot,
                settings=self._settings,
                effective_max=effective_max,
                disk_headroom_multiplier=policy.disk_headroom_multiplier,
                ram_multiplier=self._settings.validation_queue_ram_multiplier,
                min_ram_per_job_bytes=self._settings.validation_queue_min_ram_per_job_bytes,
                min_disk_per_job_bytes=self._settings.validation_queue_min_disk_per_job_bytes,
                ram_reserve_bytes=self._settings.validation_queue_ram_reserve_bytes,
                disk_reserve_bytes=self._settings.validation_queue_disk_reserve_bytes,
            )
            if not admitted:
                with self._lock:
                    self._refresh_pending_statuses_locked(
                        effective_max=effective_max,
                        queue_reason=reason if head.position == 0 else None,
                    )
                logger.debug(
                    "Job %s queued (FCFS head blocked): %s (pending=%d running=%d)",
                    head.job_id,
                    reason,
                    len(self._pending),
                    len(running_copy),
                )
                return

            concurrent = len(running_copy) + 1
            allocated = float(
                allocate_cores_per_job(
                    self._settings,
                    concurrent_jobs=concurrent,
                    ncpu=ncpu,
                )
            )
            job_added_to_running = False

            with self._lock:
                if not self._pending or self._pending[0].job_id != head.job_id:
                    continue
                if len(self._running) >= effective_max:
                    return
                next_job = self._pending.popleft()
                self._update_queue_positions()
                self._refresh_pending_statuses_locked(effective_max=effective_max)
                try:
                    next_job.allocated_cpu_cores = allocated
                    self._stamp_resource_policy(
                        next_job,
                        effective_slots=effective_max,
                        active_slots=concurrent,
                        allocated_cpu_cores=allocated,
                    )
                    if self._uses_external_workers():
                        from pegasus.services.distributed_validation_queue import get_distributed_queue

                        get_distributed_queue(self._settings).enqueue(next_job.job_id, next_job.job_dir)
                        next_job.state = JobState.RUNNING
                        next_job.started_at = time.time()
                        next_job.handle = None
                        next_job.external = True
                        self._running[next_job.job_id] = next_job
                        job_added_to_running = True
                        logger.info(
                            "Job %s dispatched to worker (FCFS) pending=%d allocated_cpu=%.0f",
                            next_job.job_id,
                            len(self._pending),
                            allocated,
                        )
                    else:
                        ok_local, local_reason = self._safe_to_spawn_local_worker(next_job)
                        if not ok_local:
                            self._pending.appendleft(next_job)
                            self._update_queue_positions()
                            self._refresh_pending_statuses_locked(
                                effective_max=effective_max,
                                queue_reason=local_reason,
                            )
                            logger.warning(
                                "Refusing local worker for job %s: %s",
                                next_job.job_id,
                                local_reason,
                            )
                            return
                        handle = self._runner.start_job(
                            next_job.job_dir,
                            allocated_cpu_cores=allocated,
                        )
                        if handle.poll() is not None:
                            detail = handle.failure_detail()
                            logger.error("Job %s worker died on start: %s", next_job.job_id, detail)
                            next_job.state = JobState.FAILED
                            next_job.finished_at = time.time()
                            self._finished[next_job.job_id] = next_job
                            handle.force_reap(reason="died on start")
                            release_job_workspace(next_job.job_dir)
                            self._write_failed_status(next_job, f"Worker died on start: {detail}")
                        else:
                            next_job.state = JobState.RUNNING
                            next_job.started_at = time.time()
                            next_job.handle = handle
                            self._running[next_job.job_id] = next_job
                            job_added_to_running = True
                            logger.info(
                                "Job %s started (FCFS) pending=%d running=%d allocated_cpu=%.0f",
                                next_job.job_id,
                                len(self._pending),
                                len(self._running),
                                allocated,
                            )
                except Exception as exc:
                    logger.exception("Failed to start worker for job %s: %s", next_job.job_id, exc)
                    next_job.state = JobState.FAILED
                    next_job.finished_at = time.time()
                    self._finished[next_job.job_id] = next_job
                    self._write_failed_status(next_job, f"Failed to start: {exc!r}")

            if job_added_to_running:
                self._rebalance_running_cpu_shares_locked()

    def _rebalance_running_cpu_shares_unlocked(self, running_jobs: list[QueuedJob]) -> None:
        if not running_jobs:
            return
        ncpu = self.cpu_cores_available()
        concurrent = len(running_jobs)
        alloc = float(
            allocate_cores_per_job(
                self._settings,
                concurrent_jobs=concurrent,
                ncpu=ncpu,
            )
        )
        for job in running_jobs:
            job.allocated_cpu_cores = alloc
            handle = job.handle
            if handle is not None and not job.external:
                if hasattr(handle, "set_cpu_quota"):
                    handle.set_cpu_quota(alloc)
                elif getattr(handle, "pid", None):
                    update_cpu_limit(int(handle.pid), alloc)

    def _rebalance_running_cpu_shares_locked(self) -> None:
        """Re-split CPU among running jobs."""
        with self._lock:
            running_jobs = list(self._running.values())
        self._rebalance_running_cpu_shares_unlocked(running_jobs)

    def _reap_finished(self) -> None:
        """Move completed/failed running jobs to the finished set and force-reap workers."""
        effective_max, _snapshot = self._drain_slot_cap()
        with self._lock:
            running_snapshot = list(self._running.items())

        finished_events: list[tuple[QueuedJob, int | None, str]] = []
        for _jid, job in running_snapshot:
            if job.external or job.handle is None:
                disk_status = _read_disk_job_status(job.job_dir)
                if disk_status == "completed":
                    finished_events.append((job, 0, "external"))
                elif disk_status == "failed":
                    finished_events.append((job, 1, "external"))
                continue
            if job.handle is None:
                continue
            if job.started_at is not None and self._runner.check_timeout(job.handle, job.started_at):
                finished_events.append((job, -9, "timed out"))
                continue
            rc = job.handle.poll()
            if rc is not None:
                finished_events.append((job, rc, "finished"))

        for job, _rc, reason in finished_events:
            if job.handle is not None and not job.external:
                try:
                    job.handle.force_reap(reason=reason)
                except Exception:
                    logger.warning("force_reap failed for job %s", job.job_id, exc_info=True)
            try:
                release_job_workspace(job.job_dir)
            except Exception:
                logger.warning(
                    "release_job_workspace failed for job %s",
                    job.job_id,
                    exc_info=True,
                )

        had_done = False
        with self._lock:
            for job, rc, reason in finished_events:
                jid = job.job_id
                if jid not in self._running:
                    continue
                job.finished_at = time.time()
                if reason == "timed out":
                    job.state = JobState.FAILED
                    timeout_s = int(self._settings.validation_job_timeout_seconds or 0)
                    self._write_failed_status(
                        job,
                        f"Validation job timed out after {timeout_s}s",
                    )
                elif reason == "external":
                    disk_status = _read_disk_job_status(job.job_dir)
                    job.state = JobState.COMPLETED if disk_status == "completed" else JobState.FAILED
                elif rc == 0:
                    job.state = JobState.COMPLETED
                else:
                    job.state = JobState.FAILED
                    detail = job.handle.failure_detail() if job.handle is not None else ""
                    self._write_failed_status(job, _failure_message(rc, detail))
                self._running.pop(jid)
                self._finished[jid] = job
                had_done = True
                logger.info(
                    "Job %s finished state=%s rc=%s elapsed=%.1fs (%s)",
                    jid,
                    job.state.value,
                    rc,
                    job.finished_at - (job.started_at or job.enqueued_at),
                    reason,
                )
                if reason != "timed out":
                    elapsed = max(1.0, job.finished_at - (job.started_at or job.enqueued_at))
                    self._avg_runtime_seconds = (self._avg_runtime_seconds * 0.8) + (elapsed * 0.2)

            if had_done and self._pending:
                self._refresh_pending_statuses_locked(effective_max=effective_max)

        if had_done:
            self._rebalance_running_cpu_shares_locked()
            self._try_start_pending()
            self._drain_event.set()

        # Prune old finished entries (keep last 500 max); drop from active index
        with self._lock:
            if len(self._finished) > 500:
                oldest = sorted(self._finished.values(), key=lambda j: j.finished_at or 0)
                for j in oldest[: len(self._finished) - 500]:
                    del self._finished[j.job_id]
                    self._active_jobs.pop(j.job_id, None)
            if len(self._active_jobs) > _ACTIVE_JOB_CAP:
                stale = sorted(
                    self._finished.values(),
                    key=lambda j: j.finished_at or 0,
                )
                for j in stale[: max(0, len(self._active_jobs) - _ACTIVE_JOB_CAP)]:
                    self._active_jobs.pop(j.job_id, None)

    def _update_queue_positions(self) -> None:
        """Recalculate 0-based position for every pending job (caller holds lock)."""
        for i, job in enumerate(self._pending):
            job.position = i

    async def shutdown(self, *, wait: bool = True) -> None:
        """Stop the drain loop and optionally wait for running jobs."""
        self._stopped = True
        self._drain_event.set()
        if self._drain_task is not None:
            self._drain_task.cancel()
            try:
                await self._drain_task
            except asyncio.CancelledError:
                pass
            self._drain_task = None
        logger.info("Validation job queue shut down (wait=%s)", wait)

    # ── Status file helpers ───────────────────────────────────────

    def _stamp_resource_policy(
        self,
        job: QueuedJob,
        *,
        effective_slots: int | None = None,
        active_slots: int | None = None,
        allocated_cpu_cores: float | None = None,
    ) -> None:
        """Write current queue resource policy into job meta.json before the worker starts."""
        meta_path = job.job_dir / "meta.json"
        if not meta_path.is_file():
            return
        try:
            meta = loads_str(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                return
            policy = self._resource_policy.clamp(
                cpu_cores=self.schedulable_cpu_cores_available(),
            )
            slots = max(1, effective_slots or self.effective_max_concurrency())
            concurrent = max(1, active_slots or len(self._running) + 1)
            schedulable = self.schedulable_cpu_cores_available()
            per_job_cpu = allocated_cpu_cores
            if per_job_cpu is None:
                per_job_cpu = float(
                    allocate_cores_per_job(
                        self._settings,
                        concurrent_jobs=concurrent,
                        ncpu=self.cpu_cores_available(),
                    )
                )
            per_job_cpu_int = max(1, int(per_job_cpu))
            avail_ram = available_worker_memory_bytes(
                api_reserve_bytes=self._settings.validation_api_memory_reserve_bytes,
            )
            global_budget = min(
                max(512 * 1024 * 1024, int(self._settings.validation_global_memory_budget_bytes)),
                avail_ram,
            )
            per_job_budget = max(512 * 1024 * 1024, global_budget // concurrent)
            src_bytes = int(meta.get("source_bytes") or 0)
            tgt_bytes = int(meta.get("target_bytes") or 0)
            combined = int(meta.get("combined_bytes") or (src_bytes + tgt_bytes))
            cols = job_column_count(meta)
            base_reconcile = self._settings.validation_partition_reconcile_workers
            if base_reconcile <= 0:
                base_reconcile = policy.effective_threads(cpu_cores=schedulable)
            from pegasus.core.workload_budget import plan_workload_budget

            budget = plan_workload_budget(
                source_bytes=max(1, src_bytes),
                target_bytes=max(1, tgt_bytes),
                compare_column_count=cols,
                cpu_cores=per_job_cpu_int,
                memory_budget_bytes=per_job_budget,
                target_duration_seconds=int(self._settings.validation_target_duration_seconds),
                requested_chunk_rows=int(self._settings.validation_reconciliation_chunk_rows),
                requested_partition_buckets=int(self._settings.validation_reconciliation_partition_buckets),
                requested_max_workers=per_job_cpu_int if per_job_cpu_int > 0 else None,
                requested_sub_partition_buckets=int(
                    self._settings.validation_reconciliation_sub_partition_buckets
                ),
                inline_native_spill=len(str(meta.get("delimiter") or "")) > 1,
            )
            throttled_reconcile = max(1, min(per_job_cpu_int, budget.max_parallel_workers))
            per_job_budget = max(512 * 1024 * 1024, per_job_budget)
            meta["resource_policy"] = {
                **policy.to_dict(),
                "memory_budget_bytes": per_job_budget,
                "chunk_rows": budget.chunk_rows,
                "partition_buckets": budget.partition_buckets,
                "effective_threads_per_job": max(
                    1,
                    min(
                        per_job_cpu_int,
                        policy.effective_threads(cpu_cores=schedulable) // concurrent,
                    ),
                ),
                "partition_reconcile_workers": throttled_reconcile,
                "concurrent_jobs_at_start": concurrent,
                "allocated_cpu_cores": round(float(per_job_cpu), 3),
                "cpu_reserve_cores": self._settings.validation_cpu_reserve_cores,
                "available_worker_ram_bytes": avail_ram,
            }
            meta_path.write_bytes(dumps_bytes(meta, indent=True))
        except (OSError, ValueError, TypeError):
            logger.warning("Could not stamp resource_policy for job %s", job.job_id, exc_info=True)

    def _write_queued_status(
        self,
        job: QueuedJob,
        *,
        effective_max: int | None = None,
        pending_count: int | None = None,
        running_jobs: int | None = None,
        queue_reason: str | None = None,
    ) -> None:
        status_path = job.job_dir / "status.json"
        eff = max(1, effective_max if effective_max is not None else self.effective_max_concurrency())
        pend = pending_count if pending_count is not None else len(self._pending)
        running = running_jobs if running_jobs is not None else len(self._running)
        wait_s = self._estimate_wait_seconds_for_position(
            queue_position=job.position,
            effective_max=eff,
            running_jobs=running,
        )
        try:
            resource_profile = None
            if status_path.is_file():
                existing = loads_str(status_path.read_text(encoding="utf-8"))
                prog = existing.get("progress") if isinstance(existing, dict) else None
                if isinstance(existing, dict) and isinstance(existing.get("resource_profile"), dict):
                    resource_profile = existing.get("resource_profile")
                if (
                    isinstance(existing, dict)
                    and existing.get("status") == "queued"
                    and isinstance(prog, dict)
                    and prog.get("queue_position") == job.position
                    and prog.get("pending_ahead") == job.position
                    and prog.get("running_jobs") == running
                    and prog.get("effective_max_concurrency") == eff
                ):
                    return
            payload: dict[str, Any] = {
                "status": "queued",
                "phase": "queued",
                "message": (
                    queue_reason
                    if queue_reason
                    else (
                        f"Accepted and queued (position {job.position + 1} of {pend}, "
                        f"starts when earlier jobs finish and resources are free)"
                    )
                ),
                "progress": {
                    "queue_position": job.position,
                    "pending_ahead": job.position,
                    "running_jobs": running,
                    "max_concurrency": self._max_concurrency,
                    "effective_max_concurrency": eff,
                    "estimated_wait_seconds": wait_s,
                    "estimated_start_epoch_s": time.time() + wait_s,
                    "enqueued_at_epoch_s": job.enqueued_at,
                    "queue_reason": queue_reason,
                    "allocated_cpu_cores": job.allocated_cpu_cores,
                },
            }
            if resource_profile is not None:
                payload["resource_profile"] = resource_profile
            _atomic_write_json(status_path, payload)
        except OSError:
            pass

    def _read_queue_reason(self, job: QueuedJob) -> str | None:
        status_path = job.job_dir / "status.json"
        if not status_path.is_file():
            return None
        try:
            st = loads_str(status_path.read_text(encoding="utf-8"))
            prog = st.get("progress") if isinstance(st, dict) else None
            if isinstance(prog, dict):
                reason = prog.get("queue_reason")
                if isinstance(reason, str) and reason.strip():
                    return reason.strip()
        except (OSError, ValueError, TypeError):
            pass
        return None

    def _estimate_wait_seconds_for_position(
        self,
        *,
        queue_position: int,
        effective_max: int,
        running_jobs: int,
    ) -> float:
        slots = max(1, effective_max)
        if running_jobs >= slots:
            batches_ahead = max(0, queue_position // slots) + 1
        else:
            free_slots = slots - running_jobs
            if queue_position < free_slots:
                return 0.0
            batches_ahead = 1 + max(0, (queue_position - free_slots) // slots)
        return float(batches_ahead * self._avg_runtime_seconds)

    def _refresh_pending_statuses_locked(
        self,
        *,
        effective_max: int,
        queue_reason: str | None = None,
    ) -> None:
        """Rewrite queued status files with fresh position and ETA (caller holds lock)."""
        eff = max(1, effective_max)
        pend = len(self._pending)
        running = len(self._running)
        for job in self._pending:
            self._write_queued_status(
                job,
                effective_max=eff,
                pending_count=pend,
                running_jobs=running,
                queue_reason=queue_reason if job.position == 0 else None,
            )

    def _write_failed_status(self, job: QueuedJob, error: str) -> None:
        status_path = job.job_dir / "status.json"
        try:
            _atomic_write_json(
                status_path,
                {
                    "status": "failed",
                    "phase": "failed",
                    "message": error,
                    "error": error,
                    "error_log": "validation_errors.log",
                    "progress": {"failed_at_epoch_s": time.time()},
                },
            )
        except OSError:
            pass


# ── Module-level singleton ────────────────────────────────────────

_queue: ValidationJobQueue | None = None
_queue_lock = threading.Lock()


def get_validation_queue(settings: Settings) -> ValidationJobQueue:
    """Get or create the singleton :class:`ValidationJobQueue`."""
    global _queue
    if _queue is not None:
        return _queue
    with _queue_lock:
        if _queue is not None:
            return _queue
        _queue = ValidationJobQueue(settings)
        return _queue


def reset_validation_queue() -> None:
    """Reset the singleton (for tests)."""
    global _queue
    _queue = None


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(dumps_bytes(payload, indent=False))
    tmp.replace(path)
