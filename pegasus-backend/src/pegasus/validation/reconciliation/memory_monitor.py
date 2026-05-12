"""Periodic RSS logging for validation worker processes."""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


def _rss_bytes() -> int:
    """Best-effort current RSS on Linux via ``/proc/self/status`` (bytes)."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:  # noqa: PTH123 — intentional procfs
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        import resource  # noqa: PLC0415

        # ru_maxrss: Linux kilobytes (peak RSS), not instantaneous
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except Exception:
        return -1


class MemoryMonitor:
    """Background thread that logs resident set size (platform-specific) on an interval."""

    __slots__ = ("_interval_sec", "_stop", "_thread")

    def __init__(self, interval_sec: float = 30.0) -> None:
        if interval_sec <= 0:
            raise ValueError("interval_sec must be positive")
        self._interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        def _run() -> None:
            while not self._stop.wait(self._interval_sec):
                rss = _rss_bytes()
                if rss >= 0:
                    logger.info("validation_memory_monitor rss_bytes=%d (~%.1f MiB)", rss, rss / (1024 * 1024))
                else:
                    logger.info("validation_memory_monitor rss unavailable on this platform")

        self._stop.clear()
        self._thread = threading.Thread(target=_run, name="pegasus-memory-monitor", daemon=True)
        self._thread.start()

    def stop(self, *, join_timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=join_timeout)
            self._thread = None
