# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T14:30:00Z
# --- END GENERATED FILE METADATA ---

"""Tests for isolated validation subprocess runner."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

from pegasus.core.config import Settings
from pegasus.services.isolated_validation_runner import IsolatedValidationHandle, IsolatedValidationRunner


def test_check_timeout_force_reaps(monkeypatch) -> None:
    settings = Settings(validation_job_timeout_seconds=1)
    runner = IsolatedValidationRunner(settings)
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    handle = IsolatedValidationHandle(proc, Path("/tmp/nonexistent.log"))
    started = time.time() - 5
    assert runner.check_timeout(handle, started) is True
    assert proc.poll() is not None


def test_check_timeout_disabled() -> None:
    settings = Settings(validation_job_timeout_seconds=0)
    runner = IsolatedValidationRunner(settings)
    handle = MagicMock()
    assert runner.check_timeout(handle, time.time() - 9999) is False
    handle.force_reap.assert_not_called()


def test_force_reap_on_finished_process() -> None:
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(0)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    proc.wait(timeout=5)
    handle = IsolatedValidationHandle(proc, Path("/tmp/nonexistent.log"))
    rc = handle.force_reap(reason="test")
    assert rc == 0
