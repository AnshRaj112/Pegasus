# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T07:48:09Z
# --- END GENERATED FILE METADATA ---

"""Spawn isolated OS processes (or a process pool) to run validation without blocking the API."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from concurrent.futures import Future
from pathlib import Path
from typing import Protocol, runtime_checkable

from pegasus.core.config import Settings
from pegasus.services.exceptions import format_validation_job_error

logger = logging.getLogger(__name__)


@runtime_checkable
class ValidationJobHandle(Protocol):
    """Started validation job (subprocess or pool future)."""

    def poll(self) -> int | None:
        """Return exit code if finished, else None."""

    def failure_detail(self) -> str:
        """Best-effort stderr / log tail for immediate failure diagnostics."""


class SubprocessValidationHandle:
    __slots__ = ("_proc", "_log_path")

    def __init__(self, proc: subprocess.Popen[bytes], log_path: Path) -> None:
        self._proc = proc
        self._log_path = log_path

    def poll(self) -> int | None:
        return self._proc.poll()

    def failure_detail(self) -> str:
        if self._log_path.is_file():
            raw = self._log_path.read_text(encoding="utf-8", errors="replace")
            return raw[-8192:] if len(raw) > 8192 else raw
        return ""


class PoolValidationHandle:
    __slots__ = ("_fut",)

    def __init__(self, fut: Future[int]) -> None:
        self._fut = fut

    def poll(self) -> int | None:
        if not self._fut.done():
            return None
        if self._fut.exception() is not None:
            return 1
        return int(self._fut.result())

    def failure_detail(self) -> str:
        exc = self._fut.exception()
        if exc is not None:
            return format_validation_job_error(exc)
        return ""


class BackgroundValidationRunner:
    """Starts ``python -m pegasus.validation.job_worker <job_dir>`` or a pooled worker."""

    __slots__ = ("_src_root", "_settings")

    def __init__(self, settings: Settings, *, pegasus_src_root: Path | None = None) -> None:
        if pegasus_src_root is None:
            pegasus_src_root = Path(__file__).resolve().parents[2]
        self._src_root = pegasus_src_root
        self._settings = settings

    def start_job(self, job_dir: Path) -> ValidationJobHandle:
        job_dir = job_dir.resolve()
        pool_n = int(self._settings.validation_worker_pool_size or 0)
        if pool_n > 0:
            from pegasus.services.validation_worker_pool import submit_pool_job

            fut = submit_pool_job(pool_n, job_dir)
            logger.info("Queued validation job in process pool job_dir=%s", job_dir)
            return PoolValidationHandle(fut)

        log_path = job_dir / "worker.log"
        log_f = open(log_path, "ab", buffering=0)  # noqa: SIM115 — closed after Popen dups fd
        try:
            env = os.environ.copy()
            prev = env.get("PYTHONPATH", "")
            root = str(self._src_root)
            env["PYTHONPATH"] = root if not prev else f"{root}{os.pathsep}{prev}"
            cmd = [sys.executable, "-m", "pegasus.validation.job_worker", str(job_dir)]
            logger.info("Starting validation worker cmd=%s cwd=%s log=%s", cmd, job_dir.parent, log_path)
            # Use subprocess.PIPE or None to inherit stdout/stderr so logs are visible in terminal
            proc = subprocess.Popen(
                cmd,
                cwd=str(job_dir.parent),
                env=env,
                stdout=None, 
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
        finally:
            log_f.close()
        return SubprocessValidationHandle(proc, log_path)
