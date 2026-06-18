# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T16:00:00Z
# --- END GENERATED FILE METADATA ---

"""Host / cgroup memory probes for adaptive validation budgeting."""

from __future__ import annotations

import os
from pathlib import Path


def cgroup_memory_limit_bytes() -> int | None:
    """Best-effort cgroup v1/v2 memory limit (Docker container cap)."""
    candidates = (
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8").strip()
            if raw in {"", "max"}:
                continue
            limit = int(raw)
            if limit > 0 and limit < 1 << 62:
                return limit
        except (OSError, ValueError):
            continue
    return None


def worker_memory_budget_bytes(settings: object) -> int:
    """Configured validation worker RAM budget (Docker worker limit or env)."""
    for attr in ("validation_global_memory_budget_bytes", "validation_memory_budget_bytes"):
        raw = getattr(settings, attr, 0) or 0
        try:
            budget = int(raw)
        except (TypeError, ValueError):
            budget = 0
        if budget > 0:
            return budget
    cgroup = cgroup_memory_limit_bytes()
    if cgroup is not None:
        reserve = int(getattr(settings, "validation_api_memory_reserve_bytes", 0) or 0)
        return max(512 * 1024 * 1024, cgroup - max(0, reserve))
    return 0


def uses_distributed_validation_workers(settings: object) -> bool:
    url = getattr(settings, "validation_distributed_queue_url", None)
    return bool(str(url or "").strip())


def admission_available_ram_bytes(settings: object) -> int:
    """RAM ceiling for queue admission (worker budget when using external workers)."""
    host_available = 0
    try:
        from pegasus.services.resource_advisor import _available_ram_bytes

        host_available = int(_available_ram_bytes())
    except Exception:
        host_available = 8 * 1024**3

    budget = worker_memory_budget_bytes(settings)
    if budget > 0 and uses_distributed_validation_workers(settings):
        return min(host_available, budget)

    cgroup = cgroup_memory_limit_bytes()
    if cgroup is not None:
        return min(host_available, cgroup)
    if budget > 0:
        return min(host_available, budget)
    return host_available


def available_worker_memory_bytes(*, api_reserve_bytes: int) -> int:
    reserve = max(256 * 1024 * 1024, int(api_reserve_bytes))
    cgroup = cgroup_memory_limit_bytes()
    if cgroup is not None:
        return max(512 * 1024 * 1024, cgroup - reserve)
    try:
        import psutil

        avail = int(psutil.virtual_memory().available)
        return max(512 * 1024 * 1024, avail - reserve)
    except Exception:
        return max(512 * 1024 * 1024, int(os.environ.get("PEGASUS_VALIDATION_MEMORY_BUDGET_BYTES", 6 * 1024**3)))
