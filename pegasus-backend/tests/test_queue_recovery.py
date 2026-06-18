# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T20:03:04+05:30
# --- END GENERATED FILE METADATA ---

"""Tests for queue recovery after crashes."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from pegasus.core.config import Settings
from pegasus.core.json_util import dumps_bytes
from pegasus.services.queue_recovery import collect_orphaned_queued_job_dirs, recover_orphaned_jobs


def test_recover_marks_stale_running_as_failed(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(validation_jobs_directory=str(tmp_path))
    job_id = uuid.uuid4()
    job_dir = tmp_path / str(job_id)
    job_dir.mkdir()
    (job_dir / "meta.json").write_bytes(dumps_bytes({}))
    (job_dir / "status.json").write_bytes(dumps_bytes({"status": "running", "phase": "validating"}))

    _requeued, failed = recover_orphaned_jobs(settings)
    assert failed == 1
    st = json.loads((job_dir / "status.json").read_text(encoding="utf-8"))
    assert st["status"] == "failed"
    assert "interrupted" in st["error"].lower()


def test_collect_orphaned_queued_jobs(tmp_path: Path) -> None:
    settings = Settings(validation_jobs_directory=str(tmp_path))
    job_id = uuid.uuid4()
    job_dir = tmp_path / str(job_id)
    job_dir.mkdir()
    (job_dir / "meta.json").write_bytes(dumps_bytes({}))
    (job_dir / "status.json").write_bytes(dumps_bytes({"status": "queued", "phase": "queued"}))

    found = collect_orphaned_queued_job_dirs(settings)
    assert len(found) == 1
    assert found[0][0] == job_id
