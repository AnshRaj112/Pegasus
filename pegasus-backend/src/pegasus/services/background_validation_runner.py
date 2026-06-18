# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Spawn isolated OS processes (or a process pool) to run validation without blocking the API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

from pegasus.core.config import Settings
from pegasus.services.isolated_validation_runner import IsolatedValidationHandle, IsolatedValidationRunner

logger = logging.getLogger(__name__)


@runtime_checkable
class ValidationJobHandle(Protocol):
    """Started validation job (isolated subprocess)."""

    def poll(self) -> int | None:
        """Return exit code if finished, else None."""

    def failure_detail(self) -> str:
        """Best-effort stderr / log tail for immediate failure diagnostics."""

    def force_reap(self, *, reason: str = "job finished") -> int | None:
        """Terminate the child process so the OS reclaims worker memory."""


class BackgroundValidationRunner:
    """Starts one short-lived ``job_worker`` child process per validation job."""

    __slots__ = ("_inner",)

    def __init__(self, settings: Settings, *, pegasus_src_root: Path | None = None) -> None:
        self._inner = IsolatedValidationRunner(settings, pegasus_src_root=pegasus_src_root)

    def start_job(
        self,
        job_dir: Path,
        *,
        allocated_cpu_cores: float | None = None,
    ) -> IsolatedValidationHandle:
        return self._inner.start_job(job_dir, allocated_cpu_cores=allocated_cpu_cores)

    def check_timeout(self, handle: IsolatedValidationHandle, started_at: float) -> bool:
        return self._inner.check_timeout(handle, started_at)
