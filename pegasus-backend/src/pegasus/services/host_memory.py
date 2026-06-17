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


def available_worker_memory_bytes(*, api_reserve_bytes: int) -> int:
    """Bytes validation workers may use on this host/container."""
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
