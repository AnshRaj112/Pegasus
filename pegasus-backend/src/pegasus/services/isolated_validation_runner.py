# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T14:00:00Z
# --- END GENERATED FILE METADATA ---

"""Spawn a short-lived child process per validation job; force-reap for memory isolation."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from pegasus.core.config import Settings

logger = logging.getLogger(__name__)

_TERMINATE_GRACE_SECONDS = 5.0


class IsolatedValidationHandle:
    """Handle to a dedicated validation subprocess (never reused)."""

    __slots__ = ("_proc", "_log_path", "_force_killed")

    def __init__(self, proc: subprocess.Popen[bytes], log_path: Path) -> None:
        self._proc = proc
        self._log_path = log_path
        self._force_killed = False

    @property
    def pid(self) -> int | None:
        return self._proc.pid

    def poll(self) -> int | None:
        return self._proc.poll()

    def failure_detail(self) -> str:
        if self._log_path.is_file():
            raw = self._log_path.read_text(encoding="utf-8", errors="replace")
            return raw[-8192:] if len(raw) > 8192 else raw
        return ""

    def force_reap(self, *, reason: str = "job finished") -> int | None:
        """Terminate or kill the child so the OS reclaims all worker memory."""
        rc = self._proc.poll()
        if rc is not None:
            try:
                self._proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self._force_kill(reason=reason)
            return rc

        logger.info("Force-reaping validation child pid=%s (%s)", self._proc.pid, reason)
        try:
            self._proc.terminate()
            rc = self._proc.wait(timeout=_TERMINATE_GRACE_SECONDS)
            return rc
        except subprocess.TimeoutExpired:
            return self._force_kill(reason=reason)

    def _force_kill(self, *, reason: str) -> int:
        self._force_killed = True
        logger.warning("Killing validation child pid=%s (%s)", self._proc.pid, reason)
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
            else:
                self._proc.kill()
        except (OSError, ProcessLookupError):
            try:
                self._proc.kill()
            except (OSError, ProcessLookupError):
                pass
        try:
            return int(self._proc.wait(timeout=_TERMINATE_GRACE_SECONDS))
        except subprocess.TimeoutExpired:
            return -9

    @property
    def was_force_killed(self) -> bool:
        return self._force_killed

    def set_cpu_quota(self, cpu_cores: float) -> None:
        from pegasus.services.cpu_quota import update_cpu_limit

        pid = self._proc.pid
        if pid is not None:
            update_cpu_limit(pid, cpu_cores)


class IsolatedValidationRunner:
    """Always starts a fresh ``job_worker`` subprocess (no shared worker pool)."""

    __slots__ = ("_src_root", "_settings")

    def __init__(self, settings: Settings, *, pegasus_src_root: Path | None = None) -> None:
        if pegasus_src_root is None:
            pegasus_src_root = Path(__file__).resolve().parents[2]
        self._src_root = pegasus_src_root
        self._settings = settings

    def start_job(
        self,
        job_dir: Path,
        *,
        allocated_cpu_cores: float | None = None,
    ) -> IsolatedValidationHandle:
        job_dir = job_dir.resolve()
        log_path = job_dir / "worker.log"
        env = os.environ.copy()
        prev = env.get("PYTHONPATH", "")
        root = str(self._src_root)
        env["PYTHONPATH"] = root if not prev else f"{root}{os.pathsep}{prev}"
        cmd = [sys.executable, "-m", "pegasus.validation.job_worker", str(job_dir)]
        logger.info("Starting isolated validation child cmd=%s job_dir=%s", cmd, job_dir)
        proc = subprocess.Popen(
            cmd,
            cwd=str(job_dir.parent),
            env=env,
            stdout=None,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )
        handle = IsolatedValidationHandle(proc, log_path)
        if allocated_cpu_cores is not None and proc.pid is not None:
            from pegasus.services.cpu_quota import apply_cpu_limit

            apply_cpu_limit(proc.pid, allocated_cpu_cores)
        return handle

    def check_timeout(self, handle: IsolatedValidationHandle, started_at: float) -> bool:
        limit = int(self._settings.validation_job_timeout_seconds or 0)
        if limit <= 0:
            return False
        if time.time() - started_at <= limit:
            return False
        handle.force_reap(reason=f"exceeded timeout {limit}s")
        return True
