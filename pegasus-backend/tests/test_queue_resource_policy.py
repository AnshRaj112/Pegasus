"""Tests for queue resource policy application."""

from __future__ import annotations

from pathlib import Path

from pegasus.core.config import Settings
from pegasus.core.json_util import dumps_bytes, loads_str
from pegasus.services.queue_resource_policy import (
    QueueResourcePolicy,
    apply_queue_policy_to_reconciliation_config,
)
from pegasus.services.validation_job_queue import ValidationJobQueue, reset_validation_queue
from pegasus.validation.reconciliation.config import ReconciliationRuntimeConfig


def test_apply_policy_sets_workers_and_disk() -> None:
    rcfg = ReconciliationRuntimeConfig(partition_buckets=64, disk_headroom_multiplier=1.5)
    policy = QueueResourcePolicy(
        threads_per_job=2,
        disk_headroom_multiplier=2.5,
        memory_budget_bytes=2 * 1024**3,
        target_duration_seconds=900,
    )
    out = apply_queue_policy_to_reconciliation_config(rcfg, policy, cpu_cores=8)
    assert out.max_parallel_workers == 2
    assert out.disk_headroom_multiplier == 2.5
    assert out.memory_budget_bytes == 2 * 1024**3


def test_queue_set_threads_and_disk() -> None:
    reset_validation_queue()
    queue = ValidationJobQueue(Settings(validation_max_concurrency=2))
    assert queue.set_threads_per_job(2) == 2
    assert queue.set_disk_headroom_multiplier(2.0) == 2.0
    stats = queue.stats
    assert stats["threads_per_job"] == 2
    assert stats["disk_headroom_multiplier"] == 2.0
    assert stats["effective_threads_per_job"] == 2


def test_stamp_resource_policy_writes_meta(tmp_path: Path) -> None:
    reset_validation_queue()
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "meta.json").write_bytes(
        dumps_bytes({"uid_column": "id", "delimiter": "auto"}, indent=True)
    )
    queue = ValidationJobQueue(Settings())
    queue.set_threads_per_job(3)
    queue.set_disk_headroom_multiplier(2.0)
    from pegasus.services.validation_job_queue import QueuedJob
    import uuid

    job = QueuedJob(job_id=uuid.uuid4(), job_dir=job_dir)
    queue._stamp_resource_policy(job)
    meta = loads_str((job_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["resource_policy"]["threads_per_job"] == 3
    assert meta["resource_policy"]["disk_headroom_multiplier"] == 2.0
    assert meta["resource_policy"]["effective_threads_per_job"] == 3
    assert int(meta["resource_policy"]["memory_budget_bytes"]) > 0
