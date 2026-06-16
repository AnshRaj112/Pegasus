# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T13:34:40Z
# --- END GENERATED FILE METADATA ---

"""Dynamic resource-aware concurrency advisor.

Inspects available RAM, disk, swap pressure, and the estimated per-job
resource cost to recommend a safe ``max_concurrency`` value.

The advisor is used by the drain loop (before starting a new job) and
by the ``GET /validate/queue`` endpoint to surface recommendations to
users and optionally auto-cap concurrency.

Design notes
------------
*  RAM per job is estimated as ``RAM_MULTIPLIER × (source_bytes + target_bytes)``.
   Polars reads the full file into memory, and reconciliation uses hash maps,
   partition buffers, and comparison DataFrames — typically 3–5× the raw CSV size.
*  Disk per job is estimated as ``disk_headroom_multiplier × (source_bytes + target_bytes)``.
   The spill workspace writes NDJSON partitions roughly 1.5× the combined CSV size.
*  A safety reserve of ``RAM_RESERVE_BYTES`` (default 1 GiB) is always kept free
   for the OS and other processes.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pegasus.core.config import Settings

logger = logging.getLogger(__name__)

# ── Tunable constants ─────────────────────────────────────────────

#: RAM multiplier per job: estimated_ram = multiplier × combined_csv_bytes.
#: Polars read + hash maps + comparison buffers ≈ 3–5× raw CSV size.
RAM_MULTIPLIER: float = 4.0

#: Minimum RAM to keep free for OS / Python runtime / other services.
RAM_RESERVE_BYTES: int = 1 * 1024**3  # 1 GiB

#: Absolute minimum RAM estimate per job even for tiny CSVs (100 MiB).
MIN_RAM_PER_JOB_BYTES: int = 100 * 1024**2

#: If we can't determine available RAM, assume this much.
FALLBACK_AVAILABLE_RAM_BYTES: int = 8 * 1024**3  # 8 GiB

#: Disk headroom multiplier default (mirrors config default).
DEFAULT_DISK_HEADROOM_MULTIPLIER: float = 1.5

#: Minimum disk per job estimate even for tiny CSVs (50 MiB).
MIN_DISK_PER_JOB_BYTES: int = 50 * 1024**2

#: Minimum disk to keep free beyond job needs (500 MiB).
DISK_RESERVE_BYTES: int = 500 * 1024**2


# ── System probes ─────────────────────────────────────────────────

def _available_ram_bytes() -> int:
    """Return *available* (not total) RAM in bytes, cross-platform."""
    # Try /proc/meminfo first (Linux — most accurate for "available")
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024  # KiB → bytes
    except (OSError, ValueError, IndexError):
        pass

    # Fallback: try os.sysconf (gives total, not available — less precise)
    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")  # type: ignore[attr-defined]
        page_size = os.sysconf("SC_PAGE_SIZE")  # type: ignore[attr-defined]
        if isinstance(pages, int) and isinstance(page_size, int) and pages > 0:
            return pages * page_size
    except (ValueError, OSError, AttributeError):
        pass

    # Windows: use ctypes GlobalMemoryStatusEx
    try:
        import ctypes
        import ctypes.wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.wintypes.DWORD),
                ("dwMemoryLoad", ctypes.wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return int(stat.ullAvailPhys)
    except (OSError, AttributeError, ImportError):
        pass

    return FALLBACK_AVAILABLE_RAM_BYTES


def _total_ram_bytes() -> int:
    """Return *total* physical RAM in bytes."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")  # type: ignore[attr-defined]
        page_size = os.sysconf("SC_PAGE_SIZE")  # type: ignore[attr-defined]
        if isinstance(pages, int) and isinstance(page_size, int) and pages > 0:
            return pages * page_size
    except (ValueError, OSError, AttributeError):
        pass

    try:
        import ctypes
        import ctypes.wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.wintypes.DWORD),
                ("dwMemoryLoad", ctypes.wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return int(stat.ullTotalPhys)
    except (OSError, AttributeError, ImportError):
        pass

    return FALLBACK_AVAILABLE_RAM_BYTES


def _available_disk_bytes(path: Path | None = None) -> int:
    """Return free bytes on the volume hosting *path* (or system temp)."""
    target = path or Path(os.environ.get("PEGASUS_VALIDATION_RECONCILIATION_TEMP_DIR", "")) or Path("/tmp")
    try:
        usage = shutil.disk_usage(target.resolve() if target.exists() else target.parent.resolve())
        return usage.free
    except OSError:
        return 100 * 1024**3  # assume 100 GiB if stat fails


def _total_disk_bytes(path: Path | None = None) -> int:
    """Return total bytes on the volume hosting *path*."""
    target = path or Path(os.environ.get("PEGASUS_VALIDATION_RECONCILIATION_TEMP_DIR", "")) or Path("/tmp")
    try:
        usage = shutil.disk_usage(target.resolve() if target.exists() else target.parent.resolve())
        return usage.total
    except OSError:
        return 100 * 1024**3


def _swap_pressure() -> float | None:
    """Return swap use fraction (0.0–1.0) or None if not available."""
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
        total = free = None
        for line in text.splitlines():
            if line.startswith("SwapTotal:"):
                total = int(line.split()[1])
            elif line.startswith("SwapFree:"):
                free = int(line.split()[1])
        if total and free is not None and total > 0:
            return (total - free) / total
    except (OSError, ValueError):
        pass
    return None


# ── Job workload estimation ───────────────────────────────────────

def estimate_streaming_job_ram_bytes(
    csv_bytes: int,
    *,
    min_ram_per_job_bytes: int,
    chunk_rows: int = 500_000,
    compare_column_count: int = 8,
) -> int:
    """Bounded RAM estimate for streaming spill (not O(file size))."""
    row_bytes = max(64, min(2048, 32 * max(1, compare_column_count + 1)))
    chunk_buffers = 2
    chunk_ram = chunk_rows * row_bytes * chunk_buffers
    overhead = 384 * 1024 * 1024
    return max(min_ram_per_job_bytes, chunk_ram + overhead)


def estimate_job_ram_bytes(
    csv_bytes: int,
    *,
    ram_multiplier: float,
    min_ram_per_job_bytes: int,
    streaming: bool = False,
    chunk_rows: int = 500_000,
    compare_column_count: int = 8,
) -> int:
    """Per-job RAM estimate — streaming model for large GCS/local spill jobs."""
    if streaming or csv_bytes >= 64 * 1024 * 1024:
        return estimate_streaming_job_ram_bytes(
            csv_bytes,
            min_ram_per_job_bytes=min_ram_per_job_bytes,
            chunk_rows=chunk_rows,
            compare_column_count=compare_column_count,
        )
    return max(min_ram_per_job_bytes, int(csv_bytes * ram_multiplier))


def _estimate_job_csv_bytes(job_dir: Path) -> int:
    """Estimate combined source + target CSV size for a job.

    Reads from the filesystem (source.csv / target.csv in job_dir) or
    falls back to meta.json if files aren't present yet.
    """
    total = 0
    for name in ("source.csv", "target.csv"):
        p = job_dir / name
        if p.is_file():
            try:
                total += p.stat().st_size
            except OSError:
                pass
            continue
        # Fallback: check meta.json for source_path / target_path
        # (used by /validate/local where CSVs are external)
        meta_path = job_dir / "meta.json"
        if meta_path.is_file():
            try:
                from pegasus.core.json_util import loads_str

                meta = loads_str(meta_path.read_text(encoding="utf-8"))
                ext_path = meta.get("source_path" if name == "source.csv" else "target_path")
                if ext_path:
                    total += Path(ext_path).stat().st_size
            except (OSError, ValueError, KeyError, TypeError):
                pass
    return total


def _running_jobs_estimated_ram(
    running_jobs: dict,
    *,
    ram_multiplier: float,
    min_ram_per_job_bytes: int,
    streaming: bool = False,
    chunk_rows: int = 500_000,
) -> int:
    """Estimate total RAM consumed by currently running jobs."""
    total = 0
    for job in running_jobs.values():
        csv_bytes = _estimate_job_csv_bytes(job.job_dir)
        total += estimate_job_ram_bytes(
            csv_bytes,
            ram_multiplier=ram_multiplier,
            min_ram_per_job_bytes=min_ram_per_job_bytes,
            streaming=streaming,
            chunk_rows=chunk_rows,
        )
    return total


# ── Resource snapshot ─────────────────────────────────────────────

@dataclass
class ResourceSnapshot:
    """Point-in-time system resource snapshot and recommendation."""

    # System resources
    total_ram_bytes: int
    available_ram_bytes: int
    total_disk_bytes: int
    available_disk_bytes: int
    cpu_cores: int
    swap_pressure: float | None

    # Per-job estimates (for the *next* pending job, or a default)
    estimated_ram_per_job_bytes: int
    estimated_disk_per_job_bytes: int

    # Already consumed by running jobs
    running_jobs_estimated_ram_bytes: int

    # Recommendations
    max_safe_by_ram: int
    max_safe_by_disk: int
    max_safe_by_cpu: int
    recommended_max_concurrency: int

    # Warnings
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API response."""
        return {
            "system": {
                "total_ram_bytes": self.total_ram_bytes,
                "available_ram_bytes": self.available_ram_bytes,
                "total_ram_gib": round(self.total_ram_bytes / 1024**3, 2),
                "available_ram_gib": round(self.available_ram_bytes / 1024**3, 2),
                "total_disk_bytes": self.total_disk_bytes,
                "available_disk_bytes": self.available_disk_bytes,
                "total_disk_gib": round(self.total_disk_bytes / 1024**3, 2),
                "available_disk_gib": round(self.available_disk_bytes / 1024**3, 2),
                "cpu_cores": self.cpu_cores,
                "swap_pressure": self.swap_pressure,
            },
            "per_job_estimate": {
                "ram_bytes": self.estimated_ram_per_job_bytes,
                "ram_mib": round(self.estimated_ram_per_job_bytes / 1024**2, 1),
                "disk_bytes": self.estimated_disk_per_job_bytes,
                "disk_mib": round(self.estimated_disk_per_job_bytes / 1024**2, 1),
            },
            "running_jobs_estimated_ram_bytes": self.running_jobs_estimated_ram_bytes,
            "limits": {
                "max_safe_by_ram": self.max_safe_by_ram,
                "max_safe_by_disk": self.max_safe_by_disk,
                "max_safe_by_cpu": self.max_safe_by_cpu,
            },
            "recommended_max_concurrency": self.recommended_max_concurrency,
            "warnings": self.warnings,
        }


# ── Main advisor function ─────────────────────────────────────────

def compute_resource_recommendation(
    *,
    running_jobs: dict | None = None,
    pending_jobs: list | None = None,
    settings: "Settings | None" = None,
    disk_headroom_multiplier: float | None = None,
    workspace_path: Path | None = None,
    ram_multiplier: float | None = None,
    ram_reserve_bytes: int | None = None,
    min_ram_per_job_bytes: int | None = None,
    min_disk_per_job_bytes: int | None = None,
    disk_reserve_bytes: int | None = None,
    threads_per_job: int | None = None,
    streaming_jobs: bool | None = None,
    chunk_rows: int | None = None,
) -> ResourceSnapshot:
    """Compute a resource-aware concurrency recommendation.

    Parameters
    ----------
    running_jobs
        Dict of currently running QueuedJob objects (keyed by job_id).
    pending_jobs
        List of pending QueuedJob objects.
    disk_headroom_multiplier
        From settings: how much disk per combined CSV bytes.
    workspace_path
        Where temp files are written (for disk free-space check).

    Returns
    -------
    ResourceSnapshot
        Contains system stats, per-job estimates, and the recommended
        ``max_concurrency``.
    """
    running_jobs = running_jobs or {}
    pending_jobs = pending_jobs or []
    warnings: list[str] = []

    if settings is not None:
        ram_multiplier = (
            ram_multiplier if ram_multiplier is not None else settings.validation_queue_ram_multiplier
        )
        ram_reserve_bytes = (
            ram_reserve_bytes
            if ram_reserve_bytes is not None
            else settings.validation_queue_ram_reserve_bytes
        )
        min_ram_per_job_bytes = (
            min_ram_per_job_bytes
            if min_ram_per_job_bytes is not None
            else settings.validation_queue_min_ram_per_job_bytes
        )
        min_disk_per_job_bytes = (
            min_disk_per_job_bytes
            if min_disk_per_job_bytes is not None
            else settings.validation_queue_min_disk_per_job_bytes
        )
        disk_reserve_bytes = (
            disk_reserve_bytes
            if disk_reserve_bytes is not None
            else settings.validation_queue_disk_reserve_bytes
        )
        disk_headroom_multiplier = (
            disk_headroom_multiplier
            if disk_headroom_multiplier is not None
            else settings.validation_reconciliation_disk_headroom_multiplier
        )

    ram_multiplier = ram_multiplier if ram_multiplier is not None else RAM_MULTIPLIER
    ram_reserve_bytes = ram_reserve_bytes if ram_reserve_bytes is not None else RAM_RESERVE_BYTES
    min_ram_per_job_bytes = (
        min_ram_per_job_bytes if min_ram_per_job_bytes is not None else MIN_RAM_PER_JOB_BYTES
    )
    min_disk_per_job_bytes = (
        min_disk_per_job_bytes if min_disk_per_job_bytes is not None else MIN_DISK_PER_JOB_BYTES
    )
    disk_reserve_bytes = disk_reserve_bytes if disk_reserve_bytes is not None else DISK_RESERVE_BYTES
    disk_headroom_multiplier = (
        disk_headroom_multiplier
        if disk_headroom_multiplier is not None
        else DEFAULT_DISK_HEADROOM_MULTIPLIER
    )

    # ── Probe system resources ────────────────────────────────────
    cpu_cores = max(1, os.cpu_count() or 1)
    total_ram = _total_ram_bytes()
    available_ram = _available_ram_bytes()
    total_disk = _total_disk_bytes(workspace_path)
    available_disk = _available_disk_bytes(workspace_path)
    swap = _swap_pressure()

    # ── Estimate per-job cost ─────────────────────────────────────
    # Use the next pending job's CSV sizes, or average of running jobs,
    # or a default for cold estimation.
    sample_csv_bytes = 0
    if pending_jobs:
        sample_csv_bytes = _estimate_job_csv_bytes(pending_jobs[0].job_dir)
    if sample_csv_bytes == 0 and running_jobs:
        sizes = [_estimate_job_csv_bytes(j.job_dir) for j in running_jobs.values()]
        sample_csv_bytes = sum(sizes) // max(1, len(sizes))
    if sample_csv_bytes == 0:
        # Default estimate: 200 MiB combined CSV
        sample_csv_bytes = 200 * 1024**2

    use_streaming_ram = streaming_jobs
    if use_streaming_ram is None and settings is not None:
        use_streaming_ram = settings.validation_gcs_streaming_only
    if use_streaming_ram is None:
        use_streaming_ram = True

    job_chunk_rows = chunk_rows
    if job_chunk_rows is None and settings is not None:
        job_chunk_rows = settings.validation_reconciliation_chunk_rows
    if job_chunk_rows is None:
        job_chunk_rows = 500_000

    estimated_ram_per_job = estimate_job_ram_bytes(
        sample_csv_bytes,
        ram_multiplier=ram_multiplier,
        min_ram_per_job_bytes=min_ram_per_job_bytes,
        streaming=use_streaming_ram,
        chunk_rows=job_chunk_rows,
    )
    estimated_disk_per_job = max(min_disk_per_job_bytes, int(sample_csv_bytes * disk_headroom_multiplier))

    # ── What running jobs already consume ─────────────────────────
    running_estimated_ram = _running_jobs_estimated_ram(
        running_jobs,
        ram_multiplier=ram_multiplier,
        min_ram_per_job_bytes=min_ram_per_job_bytes,
        streaming=use_streaming_ram,
        chunk_rows=job_chunk_rows,
    )

    # ── Compute safe limits ───────────────────────────────────────
    # RAM: (available_ram - reserve - running_ram) / per_job_ram + len(running)
    # We include currently running jobs since they already have RAM allocated.
    usable_ram = max(0, available_ram - ram_reserve_bytes)
    # How many NEW jobs can we add given current available RAM?
    new_slots_by_ram = max(0, usable_ram // max(1, estimated_ram_per_job))
    max_safe_by_ram = max(1, len(running_jobs) + new_slots_by_ram)

    # Disk: (available_disk - reserve) / per_job_disk + len(running)
    usable_disk = max(0, available_disk - disk_reserve_bytes)
    new_slots_by_disk = max(0, usable_disk // max(1, estimated_disk_per_job))
    max_safe_by_disk = max(1, len(running_jobs) + new_slots_by_disk)

    # CPU: cap parallel jobs so threads_per_job × jobs does not exceed core count (roughly)
    tpp = max(0, int(threads_per_job)) if threads_per_job is not None else 0
    slots_per_core = tpp if tpp > 0 else 1
    max_safe_by_cpu = max(1, cpu_cores // slots_per_core)

      # ── Final recommendation: minimum of all constraints ──────────
    recommended = max(1, min(max_safe_by_ram, max_safe_by_disk, max_safe_by_cpu))

    # ── Generate warnings ─────────────────────────────────────────
    if swap is not None and swap > 0.15:
        warnings.append(
            f"Swap is {swap * 100:.0f}% in use — running more parallel jobs "
            "may cause severe slowdown from memory paging."
        )

    ram_pct_used = (1 - available_ram / max(1, total_ram)) * 100
    if ram_pct_used > 80:
        warnings.append(
            f"RAM is {ram_pct_used:.0f}% used ({available_ram // 1024**2} MiB free). "
            "Consider reducing max_concurrency."
        )

    disk_pct_used = (1 - available_disk / max(1, total_disk)) * 100
    if disk_pct_used > 85:
        warnings.append(
            f"Disk is {disk_pct_used:.0f}% full ({available_disk // 1024**3} GiB free). "
            "Large validations may fail during spill."
        )

    if estimated_ram_per_job > available_ram * 0.5:
        warnings.append(
            f"A single job may need ~{estimated_ram_per_job // 1024**2} MiB RAM "
            f"but only {available_ram // 1024**2} MiB is available. "
            "Consider running only 1 job at a time."
        )

    logger.info(
        "Resource recommendation: ram_avail=%.1fG disk_avail=%.1fG "
        "per_job_ram=%.0fM per_job_disk=%.0fM "
        "safe_ram=%d safe_disk=%d safe_cpu=%d → recommended=%d",
        available_ram / 1024**3,
        available_disk / 1024**3,
        estimated_ram_per_job / 1024**2,
        estimated_disk_per_job / 1024**2,
        max_safe_by_ram,
        max_safe_by_disk,
        max_safe_by_cpu,
        recommended,
    )

    return ResourceSnapshot(
        total_ram_bytes=total_ram,
        available_ram_bytes=available_ram,
        total_disk_bytes=total_disk,
        available_disk_bytes=available_disk,
        cpu_cores=cpu_cores,
        swap_pressure=swap,
        estimated_ram_per_job_bytes=estimated_ram_per_job,
        estimated_disk_per_job_bytes=estimated_disk_per_job,
        running_jobs_estimated_ram_bytes=running_estimated_ram,
        max_safe_by_ram=max_safe_by_ram,
        max_safe_by_disk=max_safe_by_disk,
        max_safe_by_cpu=max_safe_by_cpu,
        recommended_max_concurrency=recommended,
        warnings=warnings,
    )
