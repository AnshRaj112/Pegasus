# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T08:46:25Z
# --- END GENERATED FILE METADATA ---

"""Continuous disk headroom checks during spill and partition waves."""

from __future__ import annotations

import shutil
from pathlib import Path

from pegasus.services.resource_advisor import DISK_RESERVE_BYTES


class DiskHeadroomError(OSError):
    """Raised when free disk falls below the required reserve."""


def available_disk_bytes(path: Path) -> int:
    """Free bytes on the volume hosting *path*."""
    target = path.resolve() if path.exists() else path.parent.resolve()
    try:
        return shutil.disk_usage(target).free
    except OSError:
        return 100 * 1024**3


def assert_disk_headroom(
    workspace: Path,
    *,
    required_bytes: int,
    reserve_bytes: int = DISK_RESERVE_BYTES,
) -> None:
    """Fail fast when workspace volume lacks required free space."""
    free = available_disk_bytes(workspace)
    needed = max(0, int(required_bytes)) + max(0, int(reserve_bytes))
    if free < needed:
        free_gib = free / (1024**3)
        needed_gib = needed / (1024**3)
        raise DiskHeadroomError(
            f"Insufficient disk space on workspace volume: {free_gib:.2f} GiB free, "
            f"need at least {needed_gib:.2f} GiB (required={required_bytes} reserve={reserve_bytes})"
        )


def estimate_wave_disk_bytes(
    *,
    combined_input_bytes: int,
    num_partitions: int,
    wave_size: int,
    disk_multiplier: float,
) -> int:
    """Conservative bytes needed for one reconcile wave."""
    if num_partitions <= 0:
        return int(combined_input_bytes * disk_multiplier)
    wave_fraction = min(1.0, wave_size / num_partitions) if wave_size > 0 else 1.0
    spill_estimate = int(combined_input_bytes * 0.15 * wave_fraction * 2)
    return max(spill_estimate, int(combined_input_bytes * disk_multiplier * wave_fraction))
