"""Lightweight timing (and optional RSS) logging for reconciliation phases."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


def _rss_bytes() -> int | None:
    try:
        with open("/proc/self/status", encoding="utf-8") as f:  # noqa: PTH123
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


@dataclass
class PerformanceMonitor:
    """Accumulate elapsed time and emit structured INFO logs for hot paths."""

    _label: str = "reconciliation"
    _t0: float = field(default_factory=time.perf_counter)

    def checkpoint(self, phase: str, **extra: Any) -> None:
        elapsed_ms = (time.perf_counter() - self._t0) * 1000.0
        rss = _rss_bytes()
        parts = [f"perf label={self._label!r} phase={phase!r} elapsed_ms={elapsed_ms:.1f}"]
        if rss is not None:
            parts.append(f"rss_bytes={rss}")
        for k, v in extra.items():
            parts.append(f"{k}={v!r}")
        logger.info(" ".join(parts))
