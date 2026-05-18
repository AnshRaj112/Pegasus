"""Runtime resource policy for the validation job queue (parallel jobs, threads, disk)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pegasus.core.resource_tuning import (
    align_partition_buckets_to_threads,
    cap_partition_buckets,
    effective_local_thread_cap,
    physical_cpu_count,
    physical_ram_bytes,
)

if TYPE_CHECKING:
    from pegasus.core.config import Settings
    from pegasus.validation.reconciliation.config import ReconciliationRuntimeConfig


@dataclass(frozen=True)
class QueueResourcePolicy:
    """User-tunable queue defaults applied to each validation worker at job start."""

    threads_per_job: int
    """Worker thread/process cap for partition compare; 0 = auto (use host logical CPUs)."""

    disk_headroom_multiplier: float
    """Require free disk >= multiplier × (source_bytes + target_bytes) before spill."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "threads_per_job": self.threads_per_job,
            "disk_headroom_multiplier": self.disk_headroom_multiplier,
        }

    @classmethod
    def from_settings(cls, settings: Settings) -> QueueResourcePolicy:
        disk = settings.validation_queue_disk_headroom_multiplier
        if disk is None:
            disk = settings.validation_reconciliation_disk_headroom_multiplier
        return cls(
            threads_per_job=max(0, int(settings.validation_queue_threads_per_job)),
            disk_headroom_multiplier=float(disk),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None, *, settings: Settings) -> QueueResourcePolicy:
        base = cls.from_settings(settings)
        if not data:
            return base
        threads = data.get("threads_per_job", base.threads_per_job)
        disk = data.get("disk_headroom_multiplier", base.disk_headroom_multiplier)
        return cls(
            threads_per_job=max(0, int(threads)) if threads is not None else base.threads_per_job,
            disk_headroom_multiplier=float(disk) if disk is not None else base.disk_headroom_multiplier,
        )

    def clamp(self, *, cpu_cores: int) -> QueueResourcePolicy:
        cores = max(1, cpu_cores)
        threads = self.threads_per_job
        if threads > cores:
            threads = cores
        disk = max(1.0, min(10.0, float(self.disk_headroom_multiplier)))
        return QueueResourcePolicy(threads_per_job=max(0, threads), disk_headroom_multiplier=disk)

    def effective_threads(self, *, cpu_cores: int | None = None) -> int:
        """Resolved thread cap for one worker (never below 1)."""
        cores = max(1, cpu_cores if cpu_cores is not None else physical_cpu_count())
        if self.threads_per_job <= 0:
            return cores
        return effective_local_thread_cap(self.threads_per_job, ncpu=cores)


def apply_queue_policy_to_reconciliation_config(
    rcfg: ReconciliationRuntimeConfig,
    policy: QueueResourcePolicy,
    *,
    cpu_cores: int | None = None,
) -> ReconciliationRuntimeConfig:
    """Merge queue policy into reconciliation runtime config for a single job."""
    cores = max(1, cpu_cores if cpu_cores is not None else physical_cpu_count())
    policy = policy.clamp(cpu_cores=cores)
    ram = physical_ram_bytes()

    updates: dict[str, Any] = {}
    if policy.disk_headroom_multiplier != rcfg.disk_headroom_multiplier:
        updates["disk_headroom_multiplier"] = policy.disk_headroom_multiplier

    effective_threads = policy.effective_threads(cpu_cores=cores)
    if policy.threads_per_job > 0:
        updates["max_parallel_workers"] = effective_threads
        orig_pb = rcfg.partition_buckets
        pb = cap_partition_buckets(orig_pb, ncpu=effective_threads, ram_bytes=ram)
        pb = align_partition_buckets_to_threads(pb, effective_threads)
        if pb != orig_pb:
            updates["partition_buckets"] = pb

    if not updates:
        return rcfg
    return rcfg.model_copy(update=updates)
