# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:39:41Z
# --- END GENERATED FILE METADATA ---

"""Optional process pool for validation workers (reduces per-job interpreter cold start)."""

from __future__ import annotations

import logging
import multiprocessing as mp
from concurrent.futures import Future, ProcessPoolExecutor
from pathlib import Path

logger = logging.getLogger(__name__)

_pool: ProcessPoolExecutor | None = None
_pool_workers: int = 0


def _validation_pool_initializer() -> None:
    """Import heavy deps once per pool worker (avoids 10–15s cold start per job)."""
    import pyarrow  # noqa: F401
    import polars  # noqa: F401

    from pegasus.core.config import get_settings

    get_settings()
    from pegasus.validation import job_worker as _job_worker  # noqa: F401

    _ = _job_worker


def get_validation_pool(max_workers: int) -> ProcessPoolExecutor | None:
    """Return a shared pool sized to *max_workers*, or None if *max_workers* <= 0."""
    global _pool, _pool_workers
    if max_workers <= 0:
        return None
    if _pool is not None and _pool_workers == max_workers:
        return _pool
    if _pool is not None:
        _pool.shutdown(wait=True, cancel_futures=False)
        _pool = None
    ctx = mp.get_context("spawn")
    _pool = ProcessPoolExecutor(
        max_workers=max_workers,
        mp_context=ctx,
        initializer=_validation_pool_initializer,
    )
    _pool_workers = max_workers
    logger.info("Started validation ProcessPoolExecutor max_workers=%d", max_workers)
    return _pool


def shutdown_validation_worker_pool(*, wait: bool = True) -> None:
    """Shut down the shared pool (e.g. from FastAPI lifespan)."""
    global _pool, _pool_workers
    if _pool is None:
        return
    logger.info("Shutting down validation ProcessPoolExecutor wait=%s", wait)
    _pool.shutdown(wait=wait, cancel_futures=False)
    _pool = None
    _pool_workers = 0


def submit_pool_job(max_workers: int, job_dir: Path) -> Future[int]:
    """Submit ``pegasus.validation.job_worker.run_job_directory_str`` to the pool."""
    from pegasus.validation import job_worker as job_worker_mod

    pool = get_validation_pool(max_workers)
    if pool is None:
        raise RuntimeError("submit_pool_job requires max_workers > 0")
    return pool.submit(job_worker_mod.run_job_directory_str, str(job_dir.resolve()))
