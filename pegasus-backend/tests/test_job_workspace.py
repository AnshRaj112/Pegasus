# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T14:30:00Z
# --- END GENERATED FILE METADATA ---

"""Tests for ephemeral /tmp validation workspaces."""

from __future__ import annotations

import json
from pathlib import Path

from pegasus.validation.job_workspace import (
    acquire_ephemeral_workspace,
    read_ephemeral_workspace,
    release_ephemeral_workspace,
    release_job_workspace,
    workspace_root,
)


def test_acquire_and_release_ephemeral_workspace(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-1"
    job_dir.mkdir()
    ws = acquire_ephemeral_workspace(job_dir, job_id="job-1")
    assert ws.is_dir()
    assert str(ws).startswith(str(workspace_root()))
    assert read_ephemeral_workspace(job_dir) == ws
    marker = ws / "spill.bin"
    marker.write_bytes(b"data")
    release_ephemeral_workspace(ws)
    assert not ws.exists()


def test_release_job_workspace_reads_meta_and_legacy(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-2"
    job_dir.mkdir()
    ws = acquire_ephemeral_workspace(job_dir)
    legacy = job_dir / "reconcile_workspace"
    legacy.mkdir()
    (legacy / "old.bin").write_bytes(b"x")

    release_job_workspace(job_dir)
    assert not ws.exists()
    assert not legacy.exists()


def test_release_ephemeral_workspace_is_idempotent(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-3"
    job_dir.mkdir()
    ws = acquire_ephemeral_workspace(job_dir)
    release_ephemeral_workspace(ws)
    release_ephemeral_workspace(ws)
    meta = json.loads((job_dir / "meta.json").read_text(encoding="utf-8"))
    assert "ephemeral_workspace" in meta
