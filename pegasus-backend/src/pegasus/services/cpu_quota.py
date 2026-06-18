# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Apply per-process CPU limits (cgroup v2 cpu.max or sched affinity fallback)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_CPU_PERIOD_US = 100_000


def _cgroup_v2_root() -> Path | None:
    unified = Path("/sys/fs/cgroup/cgroup.controllers")
    if unified.is_file():
        return Path("/sys/fs/cgroup")
    return None


def apply_cpu_limit(pid: int, cpu_cores: float) -> bool:
    """Limit *pid* to approximately *cpu_cores* logical CPUs."""
    cores = max(0.1, float(cpu_cores))
    if _try_cgroup_cpu_max(pid, cores):
        return True
    return _try_affinity(pid, cores)


def _try_cgroup_cpu_max(pid: int, cpu_cores: float) -> bool:
    root = _cgroup_v2_root()
    if root is None:
        return False
    quota = max(1, int(cpu_cores * _CPU_PERIOD_US))
    cg_dir = root / f"pegasus_job_{pid}"
    try:
        cg_dir.mkdir(exist_ok=True)
        (cg_dir / "cgroup.procs").write_text(f"{pid}\n", encoding="utf-8")
        (cg_dir / "cpu.max").write_text(f"{quota} {_CPU_PERIOD_US}\n", encoding="utf-8")
        logger.info("Applied cgroup cpu.max=%s for pid=%s", f"{quota} {_CPU_PERIOD_US}", pid)
        return True
    except OSError:
        logger.debug("cgroup cpu.max unavailable for pid=%s", pid, exc_info=True)
        return False


def _try_affinity(pid: int, cpu_cores: float) -> bool:
    try:
        ncpu = os.cpu_count() or 1
        count = max(1, min(ncpu, int(cpu_cores + 0.999)))
        cpus = list(range(count))
        os.sched_setaffinity(pid, cpus)
        logger.info("Applied CPU affinity %s to pid=%s (%.2f cores requested)", cpus, pid, cpu_cores)
        return True
    except (OSError, AttributeError):
        logger.debug("sched_setaffinity failed for pid=%s", pid, exc_info=True)
        return False


def update_cpu_limit(pid: int, cpu_cores: float) -> bool:
    """Re-apply CPU limit when shares are rebalanced."""
    return apply_cpu_limit(pid, cpu_cores)
