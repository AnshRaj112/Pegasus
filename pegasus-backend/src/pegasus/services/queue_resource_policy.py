# --- BEGIN GENERATED FILE METADATA ---
# Authors: github-actions[bot]
# Last edited: 2026-06-05T09:31:09Z
# --- END GENERATED FILE METADATA ---

"""Runtime resource policy for the validation job queue (parallel jobs, threads, disk)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pegasus.core.resource_tuning import effective_local_thread_cap, physical_cpu_count

if TYPE_CHECKING:
    from pegasus.core.config import Settings


@dataclass(frozen=True)
class QueueResourcePolicy:
    """User-tunable queue defaults applied to each validation worker at job start."""

    threads_per_job: int
    """Worker thread/process cap for partition compare; 0 = auto (use host logical CPUs)."""

    disk_headroom_multiplier: float
    """Require free disk >= multiplier × (source_bytes + target_bytes) before spill."""
    memory_budget_bytes: int
    """Per-job RAM budget assigned by the queue before worker start."""
    target_duration_seconds: int
    """Per-job target duration hint used by workload tuning."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "threads_per_job": self.threads_per_job,
            "disk_headroom_multiplier": self.disk_headroom_multiplier,
            "memory_budget_bytes": self.memory_budget_bytes,
            "target_duration_seconds": self.target_duration_seconds,
        }

    @classmethod
    def from_settings(cls, settings: Settings) -> QueueResourcePolicy:
        disk = settings.validation_queue_disk_headroom_multiplier
        if disk is None:
            disk = settings.validation_reconciliation_disk_headroom_multiplier
        return cls(
            threads_per_job=max(0, int(settings.validation_queue_threads_per_job)),
            disk_headroom_multiplier=float(disk),
            memory_budget_bytes=int(settings.validation_memory_budget_bytes),
            target_duration_seconds=int(settings.validation_target_duration_seconds),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, settings: Settings) -> QueueResourcePolicy:
        base = cls.from_settings(settings)
        if not data:
            return base
        threads = data.get("threads_per_job", base.threads_per_job)
        disk = data.get("disk_headroom_multiplier", base.disk_headroom_multiplier)
        mem = data.get("memory_budget_bytes", base.memory_budget_bytes)
        dur = data.get("target_duration_seconds", base.target_duration_seconds)
        return cls(
            threads_per_job=max(0, int(threads)) if threads is not None else base.threads_per_job,
            disk_headroom_multiplier=float(disk) if disk is not None else base.disk_headroom_multiplier,
            memory_budget_bytes=max(256 * 1024 * 1024, int(mem)) if mem is not None else base.memory_budget_bytes,
            target_duration_seconds=max(60, int(dur)) if dur is not None else base.target_duration_seconds,
        )

    def clamp(self, *, cpu_cores: int) -> QueueResourcePolicy:
        cores = max(1, cpu_cores)
        threads = self.threads_per_job
        if threads > cores:
            threads = cores
        disk = max(1.0, min(10.0, float(self.disk_headroom_multiplier)))
        return QueueResourcePolicy(
            threads_per_job=max(0, threads),
            disk_headroom_multiplier=disk,
            memory_budget_bytes=max(256 * 1024 * 1024, int(self.memory_budget_bytes)),
            target_duration_seconds=max(60, int(self.target_duration_seconds)),
        )

    def effective_threads(self, *, cpu_cores: int | None = None) -> int:
        """Resolved thread cap for one worker (never below 1)."""
        cores = max(1, cpu_cores if cpu_cores is not None else physical_cpu_count())
        if self.threads_per_job <= 0:
            return cores
        return effective_local_thread_cap(self.threads_per_job, ncpu=cores)


