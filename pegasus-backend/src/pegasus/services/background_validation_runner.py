"""Spawn isolated OS processes to run validation without blocking the API event loop."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class BackgroundValidationRunner:
    """Starts ``python -m pegasus.validation.job_worker <job_dir>`` with a safe ``PYTHONPATH``."""

    __slots__ = ("_src_root",)

    def __init__(self, *, pegasus_src_root: Path | None = None) -> None:
        """*pegasus_src_root* should be the directory containing the ``pegasus`` package (e.g. ``.../src``)."""
        if pegasus_src_root is None:
            pegasus_src_root = Path(__file__).resolve().parents[2]
        self._src_root = pegasus_src_root

    def start_job(self, job_dir: Path) -> subprocess.Popen[bytes]:
        env = os.environ.copy()
        prev = env.get("PYTHONPATH", "")
        root = str(self._src_root)
        env["PYTHONPATH"] = root if not prev else f"{root}{os.pathsep}{prev}"
        cmd = [sys.executable, "-m", "pegasus.validation.job_worker", str(job_dir)]
        logger.info("Starting validation worker cmd=%s cwd=%s", cmd, job_dir.parent)
        return subprocess.Popen(
            cmd,
            cwd=str(job_dir.parent),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            close_fds=True,
        )
