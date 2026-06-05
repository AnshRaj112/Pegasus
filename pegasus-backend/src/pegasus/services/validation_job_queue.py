# --- BEGIN GENERATED FILE METADATA ---
# Authors: github-actions[bot]
# Last edited: 2026-06-04T06:59:09Z
# --- END GENERATED FILE METADATA ---

"""Concurrency-limited validation job queue.

Jobs are submitted via :meth:`ValidationJobQueue.enqueue`.  A background
drain loop picks them up in FIFO order, respecting ``max_concurrency``
(the number of validation workers allowed to run simultaneously).

The queue itself is process-local and lives inside the FastAPI app.  It
replaces the old "fire-and-forget subprocess" model with an explicit
queued → running → completed/failed lifecycle.
"""

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
from pegasus.services.background_validation_runner import (
    BackgroundValidationRunner,
    ValidationJobHandle,
)
from pegasus.services.queue_resource_policy import QueueResourcePolicy
from pegasus.services.resource_advisor import (
    ResourceSnapshot,
    compute_resource_recommendation,
)

logger = logging.getLogger(__name__)


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
    position: int = 0  # 0-based queue position when queued


class ValidationJobQueue:
    """Concurrency-limited FIFO queue for validation jobs.

    Parameters
    ----------
    settings : Settings
        Application settings (reads ``validation_max_concurrency``).
    max_concurrency : int | None
        Override for the concurrency cap.  ``None`` reads from *settings*.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        max_concurrency: int | None = None,
    ) -> None:
        mc = max_concurrency if max_concurrency is not None else settings.validation_max_concurrency
        self._max_concurrency: int = max(1, mc)
        self._settings = settings
        self._runner = BackgroundValidationRunner(settings)
        self._auto_tune_enabled: bool = settings.validation_auto_tune_enabled
        self._resource_policy: QueueResourcePolicy = QueueResourcePolicy.from_settings(settings)

        # Ordered queue of pending jobs (FIFO)
        self._pending: deque[QueuedJob] = deque()
        # Currently running jobs keyed by job_id
        self._running: dict[uuid.UUID, QueuedJob] = {}
        # Completed/failed jobs (kept in memory briefly for status queries)
        self._finished: dict[uuid.UUID, QueuedJob] = {}
        # All jobs index for fast lookup
        self._all_jobs: dict[uuid.UUID, QueuedJob] = {}
        # Last resource snapshot (cached for stats endpoint)
        self._last_resource_snapshot: ResourceSnapshot | None = None

        self._lock = threading.Lock()
        self._drain_event = asyncio.Event()
        self._drain_task: asyncio.Task[None] | None = None
        self._stopped = False
        self._avg_runtime_seconds: float = 15 * 60

        logger.info(
            "ValidationJobQueue created max_concurrency=%d auto_tune=%s threads_per_job=%d disk_mult=%.2f mem_budget_mib=%.1f",
            self._max_concurrency,
            self._auto_tune_enabled,
            self._resource_policy.threads_per_job,
            self._resource_policy.disk_headroom_multiplier,
            self._resource_policy.memory_budget_bytes / (1024**2),
        )

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

    def set_max_concurrency(self, value: int) -> int:
        """Update the concurrency cap at runtime.  Returns the clamped value actually set.

        The new limit takes effect on the next drain-loop tick.  If *value* is
        greater than the current number of running jobs, pending jobs will be
        promoted immediately.  If it is smaller, no running jobs are killed —
        the queue simply waits for slots to free up naturally.
        """
        clamped = max(1, value)
        with self._lock:
            old = self._max_concurrency
            self._max_concurrency = clamped
        logger.info("max_concurrency changed %d → %d", old, clamped)
        # Wake the drain loop so it can start more pending jobs if slots opened
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
        """User cap after optional auto-tune (what the drain loop uses)."""
        effective = self._max_concurrency
        if self._auto_tune_enabled:
            try:
                snap = snapshot or self.resource_recommendation()
                effective = min(self._max_concurrency, snap.recommended_max_concurrency)
            except Exception:
                logger.warning("Resource advisor failed, using user-set max_concurrency", exc_info=True)
        return max(1, effective)

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
                "total_tracked": len(self._all_jobs),
            }
        snapshot = self.resource_recommendation()
        result["effective_max_concurrency"] = self.effective_max_concurrency(snapshot=snapshot)
        result["resource_advisor"] = snapshot.to_dict()
        return result

    def enqueue(self, job_id: uuid.UUID, job_dir: Path) -> QueuedJob:
        """Add a job to the queue.  Returns the :class:`QueuedJob` immediately."""
        job = QueuedJob(job_id=job_id, job_dir=job_dir.resolve())
        with self._lock:
            job.position = len(self._pending)
            self._pending.append(job)
            self._all_jobs[job_id] = job
            self._update_queue_positions()
            self._refresh_pending_statuses_locked(effective_max=max(1, self._max_concurrency))
            logger.info(
                "Job %s enqueued position=%d pending=%d running=%d/%d",
                job_id,
                job.position,
                len(self._pending),
                len(self._running),
                self._max_concurrency,
            )

        # Write queue position to status.json so the poll endpoint can show it
        self._write_queued_status(job)

        # Signal the drain loop
        self._drain_event.set()
        return job

    def get_job(self, job_id: uuid.UUID) -> QueuedJob | None:
        """Return the in-memory job record, or None if unknown."""
        with self._lock:
            return self._all_jobs.get(job_id)

    def get_queue_position(self, job_id: uuid.UUID) -> int | None:
        """0-based position in the pending queue, or None if not queued."""
        with self._lock:
            for i, job in enumerate(self._pending):
                if job.job_id == job_id:
                    return i
            return None

    def list_jobs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return a snapshot of all tracked jobs (most recent first)."""
        with self._lock:
            jobs = sorted(self._all_jobs.values(), key=lambda j: j.enqueued_at, reverse=True)
            running_jobs = len(self._running)
            max_concurrency = self._max_concurrency
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
                        effective_max=max_concurrency,
                        running_jobs=running_jobs,
                    )
                    if j.state == JobState.QUEUED
                    else None
                ),
                "estimated_start_epoch_s": (
                    time.time()
                    + self._estimate_wait_seconds_for_position(
                        queue_position=j.position,
                        effective_max=max_concurrency,
                        running_jobs=running_jobs,
                    )
                    if j.state == JobState.QUEUED
                    else None
                ),
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
        """Start as many pending jobs as concurrency slots allow.

        When ``auto_tune_enabled`` is True, the effective concurrency cap
        is the **minimum** of the user-set ``max_concurrency`` and the
        resource advisor's recommendation.  This prevents starting more
        jobs than the system can safely handle.
        """
        effective_max = self.effective_max_concurrency()
        if self._auto_tune_enabled and effective_max < self._max_concurrency:
            snapshot = self._last_resource_snapshot
            if snapshot is not None:
                logger.info(
                    "Auto-tune: capping concurrency from %d to %d "
                    "(ram_safe=%d disk_safe=%d cpu_safe=%d)",
                    self._max_concurrency,
                    effective_max,
                    snapshot.max_safe_by_ram,
                    snapshot.max_safe_by_disk,
                    snapshot.max_safe_by_cpu,
                )

        with self._lock:
            while self._pending and len(self._running) < effective_max:
                job = self._pending.popleft()
                self._update_queue_positions()
                self._refresh_pending_statuses_locked(effective_max=effective_max)
                try:
                    self._stamp_resource_policy(job, effective_slots=effective_max)
                    handle = self._runner.start_job(job.job_dir)
                    # Quick sanity: did it die immediately?
                    if handle.poll() is not None:
                        detail = handle.failure_detail()
                        logger.error("Job %s worker died on start: %s", job.job_id, detail)
                        job.state = JobState.FAILED
                        job.finished_at = time.time()
                        self._finished[job.job_id] = job
                        self._write_failed_status(job, f"Worker died on start: {detail}")
                        continue
                except Exception as exc:
                    logger.exception("Failed to start worker for job %s: %s", job.job_id, exc)
                    job.state = JobState.FAILED
                    job.finished_at = time.time()
                    self._finished[job.job_id] = job
                    self._write_failed_status(job, f"Failed to start: {exc!r}")
                    continue

                job.state = JobState.RUNNING
                job.started_at = time.time()
                job.handle = handle
                self._running[job.job_id] = job
                logger.info(
                    "Job %s started running=%d/%d pending=%d",
                    job.job_id,
                    len(self._running),
                    self._max_concurrency,
                    len(self._pending),
                )

    def _reap_finished(self) -> None:
        """Move completed/failed running jobs to the finished set."""
        with self._lock:
            done_ids = []
            for jid, job in self._running.items():
                if job.handle is not None:
                    rc = job.handle.poll()
                    if rc is not None:
                        job.finished_at = time.time()
                        job.state = JobState.COMPLETED if rc == 0 else JobState.FAILED
                        done_ids.append(jid)
                        logger.info(
                            "Job %s finished state=%s rc=%s elapsed=%.1fs",
                            jid,
                            job.state.value,
                            rc,
                            job.finished_at - (job.started_at or job.enqueued_at),
                        )
                        elapsed = max(1.0, job.finished_at - (job.started_at or job.enqueued_at))
                        self._avg_runtime_seconds = (self._avg_runtime_seconds * 0.8) + (elapsed * 0.2)

            for jid in done_ids:
                job = self._running.pop(jid)
                self._finished[jid] = job

            # Notify pending are now eligible to start
            if done_ids and self._pending:
                # Will be picked up on next loop iteration
                self._refresh_pending_statuses_locked(effective_max=max(1, self._max_concurrency))

        # Prune old finished entries (keep last 500 max)
        with self._lock:
            if len(self._finished) > 500:
                oldest = sorted(self._finished.values(), key=lambda j: j.finished_at or 0)
                for j in oldest[: len(self._finished) - 500]:
                    del self._finished[j.job_id]
                    del self._all_jobs[j.job_id]

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

    def _stamp_resource_policy(self, job: QueuedJob, *, effective_slots: int | None = None) -> None:
        """Write current queue resource policy into job meta.json before the worker starts."""
        meta_path = job.job_dir / "meta.json"
        if not meta_path.is_file():
            return
        try:
            meta = loads_str(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                return
            policy = self._resource_policy.clamp(cpu_cores=self.cpu_cores_available())
            slots = max(1, effective_slots or self.effective_max_concurrency())
            # Split global budget fairly across active slots to avoid over-commit during bursts.
            global_budget = max(512 * 1024 * 1024, int(self._settings.validation_global_memory_budget_bytes))
            per_job_budget = max(512 * 1024 * 1024, global_budget // slots)
            meta["resource_policy"] = {
                **policy.to_dict(),
                "memory_budget_bytes": per_job_budget,
                "effective_threads_per_job": policy.effective_threads(
                    cpu_cores=self.cpu_cores_available()
                ),
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
            if status_path.is_file():
                existing = loads_str(status_path.read_text(encoding="utf-8"))
                prog = existing.get("progress") if isinstance(existing, dict) else None
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
            _atomic_write_json(
                status_path,
                {
                    "status": "queued",
                    "phase": "queued",
                    "message": (
                        f"Waiting in queue (position {job.position + 1} of {pend}, "
                        f"estimated wait {int(wait_s)}s)"
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
                    },
                },
            )
        except OSError:
            pass

    def _estimate_wait_seconds_for_position(
        self,
        *,
        queue_position: int,
        effective_max: int,
        running_jobs: int,
    ) -> float:
        if queue_position <= 0 and running_jobs < max(1, effective_max):
            return 0.0
        slots = max(1, effective_max)
        groups_ahead = queue_position // slots
        running_penalty = 1 if running_jobs >= slots else 0
        return float((groups_ahead + running_penalty) * self._avg_runtime_seconds)

    def _refresh_pending_statuses_locked(self, *, effective_max: int) -> None:
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
            )

    def _write_failed_status(self, job: QueuedJob, error: str) -> None:
        status_path = job.job_dir / "status.json"
        try:
            _atomic_write_json(
                status_path,
                {
                    "status": "failed",
                    "phase": "failed",
                    "message": "Job failed before validation started",
                    "error": error,
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
