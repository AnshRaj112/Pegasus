"""Disk free-space checks before large spill/sort workloads."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from .exceptions import ReconciliationError

logger = logging.getLogger(__name__)


def ensure_disk_headroom(
    path: Path,
    required_free_bytes: int,
    *,
    label: str = "reconciliation workspace",
) -> None:
    """Raise :class:`ReconciliationError` if the volume hosting *path* lacks free bytes.

    Parameters
    ----------
    path
        Any path on the target filesystem (parent directories are created as needed).
    required_free_bytes
        Minimum ``shutil.disk_usage`` free bytes required before starting spill/sort.
    label
        Human-readable name for error messages.
    """
    if required_free_bytes <= 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve()
    try:
        usage = shutil.disk_usage(resolved)
    except OSError as exc:
        logger.warning("Could not stat disk usage for %s: %s", resolved, exc)
        return
    free = usage.free
    if free < required_free_bytes:
        need_gib = required_free_bytes / (1024**3)
        free_gib = free / (1024**3)
        msg = (
            f"Insufficient disk space for {label}: need at least {need_gib:.2f} GiB free "
            f"({required_free_bytes} bytes) but only {free_gib:.2f} GiB ({free} bytes) available on "
            f"volume of {resolved}."
        )
        logger.error(msg)
        raise ReconciliationError(msg)
    logger.info(
        "Disk headroom OK for %s: free=%.2f GiB required=%.2f GiB path=%s",
        label,
        free / (1024**3),
        required_free_bytes / (1024**3),
        resolved,
    )
