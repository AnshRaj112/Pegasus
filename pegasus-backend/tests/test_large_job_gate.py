# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:22:54Z
# --- END GENERATED FILE METADATA ---

"""Tests for large-job concurrency cap."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.services.job_size_estimate import estimate_job_combined_bytes
from pegasus.services.validation_job_queue import QueuedJob, ValidationJobQueue


def test_estimate_job_combined_bytes_from_meta_paths(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    src = tmp_path / "big.csv"
    src.write_bytes(b"x" * (10 * 1024 * 1024))
    meta = {"source_path": str(src), "target_path": str(src)}
    (job_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    assert estimate_job_combined_bytes(job_dir) == 20 * 1024 * 1024


def test_large_job_gate_caps_concurrency(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    src = tmp_path / "big.csv"
    src.write_bytes(b"x" * (10 * 1024 * 1024))
    meta = {"source_path": str(src), "target_path": str(src)}
    (job_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    settings = Settings(
        validation_large_job_bytes=8 * 1024 * 1024,
        validation_max_concurrency=4,
        validation_auto_tune_enabled=False,
    )
    queue = ValidationJobQueue(settings)
    queue._pending.append(QueuedJob(job_id=uuid.uuid4(), job_dir=job_dir))  # noqa: SLF001

    cap, _ = queue._drain_slot_cap()  # noqa: SLF001
    assert cap == 1
