# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T05:59:50Z
# --- END GENERATED FILE METADATA ---

"""Host-aware defaults for validation / reconciliation (partitions, threads, swap hints)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def physical_cpu_count() -> int:
    return max(1, int(os.cpu_count() or 1))


def physical_ram_bytes() -> int | None:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if isinstance(pages, int) and isinstance(page_size, int) and pages > 0 and page_size > 0:
            return pages * page_size
    except (ValueError, OSError, AttributeError):
        pass
    return None


def meminfo_swap_kib() -> tuple[int, int] | None:
    """Return ``(SwapTotal_kiB, SwapFree_kiB)`` from ``/proc/meminfo``, or ``None``."""
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    total: int | None = None
    free: int | None = None
    for line in text.splitlines():
        if line.startswith("SwapTotal:"):
            total = int(line.split()[1])
        elif line.startswith("SwapFree:"):
            free = int(line.split()[1])
    if total is None or free is None:
        return None
    return total, free


def swap_use_fraction() -> float | None:
    """Fraction of swap space in use (0..1), or ``None`` if swap is unavailable / unknown."""
    info = meminfo_swap_kib()
    if info is None:
        return None
    total, free = info
    if total <= 0:
        return None
    return (total - free) / total


def log_swap_pressure_warning(log: logging.Logger = logger) -> None:
    """Emit a preflight warning when swap is already backing memory (hurts validation latency)."""
    info = meminfo_swap_kib()
    if info is None:
        return
    total, free = info
    if total <= 0:
        return
    used = total - free
    frac = used / total
    if frac < 0.10:
        return
    log.warning(
        "Swap is %.1f%% in use (%d / %d KiB); validation can be very slow if the system keeps paging. "
        "Consider freeing RAM, expanding swap, or reducing concurrent load.",
        100.0 * frac,
        used,
        total,
    )


def max_reconciliation_partition_buckets(
    *,
    ncpu: int | None = None,
    ram_bytes: int | None = None,
) -> int:
    """Upper bound for hash partition count: fewer buckets on low-RAM / few-core hosts."""
    cores = physical_cpu_count() if ncpu is None else max(1, ncpu)
    ram = physical_ram_bytes() if ram_bytes is None else ram_bytes
    if ram is None:
        ram = 16 * 1024 * 1024 * 1024
    gib = ram / (1024**3)
    if gib < 8:
        cap = min(32, max(16, cores * 4))
    elif gib < 16:
        cap = min(48, max(16, cores * 8))
    elif gib < 32:
        cap = min(64, max(16, cores * 12))
    elif gib < 64:
        cap = min(256, max(16, cores * 16))
    elif gib < 128:
        cap = min(1024, max(16, cores * 32))
    else:
        cap = min(8192, max(16, cores * 64))
    return max(16, min(cap, max(16, cores * 64)))


def recommended_reconciliation_partition_buckets() -> int:
    """Default ``validation_reconciliation_partition_buckets`` when unset in the environment."""
    cores = physical_cpu_count()
    ram = physical_ram_bytes()
    upper = max_reconciliation_partition_buckets(ncpu=cores, ram_bytes=ram)
    return int(max(16, min(upper, cores * 8)))


def cap_partition_buckets(
    requested: int,
    *,
    ncpu: int | None = None,
    ram_bytes: int | None = None,
    combined_file_bytes: int = 0,
) -> int:
    """Cap partition count by host RAM, but raise the floor for large fingerprint-only spill jobs."""
    mx = max_reconciliation_partition_buckets(ncpu=ncpu, ram_bytes=ram_bytes)
    file_floor = 16
    if combined_file_bytes >= 512 * 1024**2:
        file_floor = 128
    if combined_file_bytes >= 2 * 1024**3:
        file_floor = 256
    if combined_file_bytes >= 8 * 1024**3:
        file_floor = 512
    if combined_file_bytes >= 20 * 1024**3:
        file_floor = 1024
    effective_cap = max(mx, file_floor)
    return max(1, max(file_floor, min(int(requested), effective_cap)))


def effective_local_thread_cap(requested_threads: int, *, ncpu: int | None = None) -> int:
    """Resolve a requested thread count (0 => full machine) capped to logical CPU count."""
    cores = physical_cpu_count() if ncpu is None else max(1, ncpu)
    t = requested_threads if requested_threads > 0 else cores
    return max(1, min(int(t), cores))


def align_partition_buckets_to_threads(buckets: int, parallel_workers: int) -> int:
    """Avoid hundreds of partition rounds on small machines (``~workers * 16`` soft ceiling)."""
    if buckets < 1:
        return 1
    dt = max(1, parallel_workers)
    soft_cap = max(16, dt * 16)
    return max(1, min(int(buckets), soft_cap))
