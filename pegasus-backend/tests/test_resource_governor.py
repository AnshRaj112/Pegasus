# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T10:31:41+05:30
# --- END GENERATED FILE METADATA ---

"""Tests for job resource metadata and admission governor."""

from __future__ import annotations

import uuid
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.core.json_util import dumps_bytes
from pegasus.services.job_resource_meta import estimate_job_csv_bytes, stamp_resource_sizes
from pegasus.services.resource_advisor import compute_resource_recommendation
from pegasus.services.resource_governor import can_admit_job
from pegasus.services.validation_job_queue import QueuedJob


def test_estimate_job_bytes_from_meta(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    meta = stamp_resource_sizes(
        {},
        source_bytes=20 * 1024**3,
        target_bytes=20 * 1024**3,
        column_count=12,
    )
    (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))
    assert estimate_job_csv_bytes(job_dir) == 40 * 1024**3


def test_admission_rejects_second_large_job_on_small_host(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(
        validation_auto_tune_enabled=True,
        validation_gcs_streaming_only=True,
        validation_utilization_slack=0.70,
        validation_queue_ram_reserve_bytes=2 * 1024**3,
    )

    def fake_available_ram() -> int:
        return 15 * 1024**3

    monkeypatch.setattr(
        "pegasus.services.resource_advisor._available_ram_bytes",
        fake_available_ram,
    )
    monkeypatch.setattr(
        "pegasus.services.resource_advisor._total_ram_bytes",
        lambda: 15 * 1024**3,
    )
    monkeypatch.setattr(
        "pegasus.services.resource_advisor._available_disk_bytes",
        lambda _path=None: 200 * 1024**3,
    )
    monkeypatch.setattr(
        "pegasus.services.resource_advisor._total_disk_bytes",
        lambda _path=None: 200 * 1024**3,
    )
    monkeypatch.setattr("pegasus.services.resource_advisor.os.cpu_count", lambda: 4)

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    meta = stamp_resource_sizes({}, source_bytes=20 * 1024**3, target_bytes=20 * 1024**3)
    (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))

    running_job = QueuedJob(job_id=uuid.uuid4(), job_dir=job_dir)
    pending_job = QueuedJob(job_id=uuid.uuid4(), job_dir=job_dir)

    snapshot = compute_resource_recommendation(
        running_jobs={running_job.job_id: running_job},
        pending_jobs=[pending_job],
        settings=settings,
    )

    admitted, reason = can_admit_job(
        pending_job,
        {running_job.job_id: running_job},
        snapshot,
        settings=settings,
        effective_max=max(1, snapshot.recommended_max_concurrency),
        disk_headroom_multiplier=1.5,
        ram_multiplier=settings.validation_queue_ram_multiplier,
        min_ram_per_job_bytes=settings.validation_queue_min_ram_per_job_bytes,
        min_disk_per_job_bytes=settings.validation_queue_min_disk_per_job_bytes,
        ram_reserve_bytes=settings.validation_queue_ram_reserve_bytes,
        disk_reserve_bytes=settings.validation_queue_disk_reserve_bytes,
    )
    assert not admitted
    assert reason
    assert "large job" in reason.lower()


def test_admission_uses_worker_budget_not_host_ram(monkeypatch) -> None:
    settings = Settings(
        validation_global_memory_budget_bytes=11 * 1024**3,
        validation_distributed_queue_url="redis://localhost:6379/0",
    )
    monkeypatch.setattr(
        "pegasus.services.resource_advisor._available_ram_bytes",
        lambda: 64 * 1024**3,
    )
    from pegasus.services.host_memory import admission_available_ram_bytes

    assert admission_available_ram_bytes(settings) == 11 * 1024**3
