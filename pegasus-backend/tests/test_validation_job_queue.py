"""Tests for the validation job queue and resource advisor integration."""

from __future__ import annotations

import uuid
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.core.json_util import loads_str
from pegasus.services.resource_advisor import compute_resource_recommendation
from pegasus.services.validation_job_queue import ValidationJobQueue, reset_validation_queue


def test_set_max_concurrency_accepts_values_above_legacy_cap() -> None:
    reset_validation_queue()
    settings = Settings(validation_max_concurrency=2)
    queue = ValidationJobQueue(settings)
    assert queue.set_max_concurrency(64) == 64
    assert queue.max_concurrency == 64


def test_auto_tune_initializes_from_settings() -> None:
    reset_validation_queue()
    settings = Settings(validation_auto_tune_enabled=False)
    queue = ValidationJobQueue(settings)
    assert queue.stats["auto_tune_enabled"] is False


def test_resource_recommendation_not_capped_at_32() -> None:
    snapshot = compute_resource_recommendation(
        settings=Settings(
            validation_queue_ram_reserve_bytes=0,
            validation_queue_disk_reserve_bytes=0,
            validation_queue_min_ram_per_job_bytes=1024 * 1024,
            validation_queue_min_disk_per_job_bytes=1024 * 1024,
            validation_queue_ram_multiplier=1.0,
            validation_reconciliation_disk_headroom_multiplier=1.0,
        ),
    )
    # With tiny per-job floors and no reserves, recommendation can exceed 32 on large hosts.
    assert snapshot.recommended_max_concurrency >= 1
    assert snapshot.recommended_max_concurrency == min(
        snapshot.max_safe_by_ram,
        snapshot.max_safe_by_disk,
        snapshot.max_safe_by_cpu,
    )


def test_effective_max_concurrency_respects_auto_tune() -> None:
    reset_validation_queue()
    settings = Settings(validation_max_concurrency=100, validation_auto_tune_enabled=True)
    queue = ValidationJobQueue(settings)
    queue.set_max_concurrency(100)
    effective = queue.effective_max_concurrency()
    recommended = queue.resource_recommendation().recommended_max_concurrency
    assert effective == min(100, recommended)


def test_queued_status_includes_wait_estimates(tmp_path: Path) -> None:
    reset_validation_queue()
    queue = ValidationJobQueue(Settings(validation_max_concurrency=2))
    j1 = tmp_path / "job1"
    j2 = tmp_path / "job2"
    j1.mkdir()
    j2.mkdir()
    q1 = queue.enqueue(uuid.uuid4(), j1)
    queue.enqueue(uuid.uuid4(), j2)
    st1 = loads_str((q1.job_dir / "status.json").read_text(encoding="utf-8"))
    st2 = loads_str((j2 / "status.json").read_text(encoding="utf-8"))
    assert "estimated_wait_seconds" in st1.get("progress", {})
    assert "estimated_wait_seconds" in st2.get("progress", {})
    assert "effective_max_concurrency" in st2.get("progress", {})


def test_list_jobs_includes_eta_for_queued(tmp_path: Path) -> None:
    reset_validation_queue()
    queue = ValidationJobQueue(Settings(validation_max_concurrency=2))
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    queue.enqueue(uuid.uuid4(), job_dir)
    rows = queue.list_jobs(limit=10)
    assert rows
    assert rows[0]["state"] == "queued"
    assert rows[0]["estimated_wait_seconds"] is not None
    assert rows[0]["estimated_start_epoch_s"] is not None
