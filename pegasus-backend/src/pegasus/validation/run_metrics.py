"""Collect and log per-validation resource and timing metrics (Docker-friendly stdout)."""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pegasus.services.resource_advisor import (
    _available_disk_bytes,
    _available_ram_bytes,
    _swap_pressure,
    _total_disk_bytes,
    _total_ram_bytes,
)

logger = logging.getLogger(__name__)


def _rss_bytes() -> int:
    try:
        with open("/proc/self/status", encoding="utf-8") as f:  # noqa: PTH123
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        import resource  # noqa: PLC0415

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except Exception:
        return -1


def _dir_size_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    try:
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


@dataclass
class SystemSnapshot:
    cpu_cores: int
    total_ram_bytes: int
    available_ram_bytes: int
    total_disk_bytes: int
    available_disk_bytes: int
    swap_pressure: float | None
    process_rss_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_cores": self.cpu_cores,
            "total_ram_bytes": self.total_ram_bytes,
            "available_ram_bytes": self.available_ram_bytes,
            "total_ram_mib": round(self.total_ram_bytes / (1024**2), 1),
            "available_ram_mib": round(self.available_ram_bytes / (1024**2), 1),
            "total_disk_bytes": self.total_disk_bytes,
            "available_disk_bytes": self.available_disk_bytes,
            "total_disk_gib": round(self.total_disk_bytes / (1024**3), 2),
            "available_disk_gib": round(self.available_disk_bytes / (1024**3), 2),
            "swap_pressure": self.swap_pressure,
            "process_rss_bytes": self.process_rss_bytes if self.process_rss_bytes >= 0 else None,
            "process_rss_mib": round(self.process_rss_bytes / (1024**2), 1) if self.process_rss_bytes >= 0 else None,
        }


def capture_system_snapshot(*, workspace: Path | None = None) -> SystemSnapshot:
    ws = workspace
    rss = _rss_bytes()
    return SystemSnapshot(
        cpu_cores=max(1, os.cpu_count() or 1),
        total_ram_bytes=_total_ram_bytes(),
        available_ram_bytes=_available_ram_bytes(),
        total_disk_bytes=_total_disk_bytes(ws),
        available_disk_bytes=_available_disk_bytes(ws),
        swap_pressure=_swap_pressure(),
        process_rss_bytes=rss,
    )


@dataclass
class ValidationRunMetrics:
    job_id: str
    started_at_epoch_s: float = field(default_factory=time.time)
    completed_at_epoch_s: float | None = None
    upload_seconds: float = 0.0
    queue_wait_seconds: float | None = None
    validation_seconds: float | None = None
    total_seconds: float | None = None
    start_snapshot: SystemSnapshot | None = None
    end_snapshot: SystemSnapshot | None = None
    peak_rss_bytes: int | None = None
    job_dir_bytes: int | None = None
    parallel_jobs_running: int | None = None
    max_concurrency: int | None = None
    effective_max_concurrency: int | None = None
    threads_per_job: int | None = None
    effective_threads_per_job: int | None = None
    partition_workers: int | None = None
    resource_policy: dict[str, Any] | None = None
    source_bytes: int | None = None
    target_bytes: int | None = None
    first_poll_after_complete_seconds: float | None = None

    def note_rss(self, rss_bytes: int) -> None:
        if rss_bytes < 0:
            return
        if self.peak_rss_bytes is None or rss_bytes > self.peak_rss_bytes:
            self.peak_rss_bytes = rss_bytes

    def finalize(
        self,
        *,
        job_dir: Path,
        validation_seconds: float,
        upload_seconds: float,
        workspace: Path | None = None,
    ) -> None:
        self.completed_at_epoch_s = time.time()
        self.validation_seconds = validation_seconds
        self.upload_seconds = upload_seconds
        self.total_seconds = upload_seconds + validation_seconds
        self.end_snapshot = capture_system_snapshot(workspace=workspace)
        self.job_dir_bytes = _dir_size_bytes(job_dir)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "job_id": self.job_id,
            "started_at_epoch_s": self.started_at_epoch_s,
            "completed_at_epoch_s": self.completed_at_epoch_s,
            "upload_seconds": self.upload_seconds,
            "queue_wait_seconds": self.queue_wait_seconds,
            "validation_seconds": self.validation_seconds,
            "total_seconds": self.total_seconds,
            "peak_rss_bytes": self.peak_rss_bytes,
            "peak_rss_mib": round(self.peak_rss_bytes / (1024**2), 1) if self.peak_rss_bytes else None,
            "job_dir_bytes": self.job_dir_bytes,
            "job_dir_mib": round(self.job_dir_bytes / (1024**2), 1) if self.job_dir_bytes is not None else None,
            "parallel_jobs_running": self.parallel_jobs_running,
            "max_concurrency": self.max_concurrency,
            "effective_max_concurrency": self.effective_max_concurrency,
            "threads_per_job": self.threads_per_job,
            "effective_threads_per_job": self.effective_threads_per_job,
            "partition_workers": self.partition_workers,
            "source_bytes": self.source_bytes,
            "target_bytes": self.target_bytes,
            "first_poll_after_complete_seconds": self.first_poll_after_complete_seconds,
        }
        if self.start_snapshot is not None:
            out["system_at_start"] = self.start_snapshot.to_dict()
        if self.end_snapshot is not None:
            out["system_at_end"] = self.end_snapshot.to_dict()
        if self.resource_policy is not None:
            out["resource_policy"] = self.resource_policy
        return out

    def log_summary(self) -> None:
        """Emit one structured INFO line visible in ``docker compose logs -f backend``."""
        d = self.to_dict()
        logger.info(
            "validation_run_metrics job_id=%s "
            "upload_s=%.2f queue_wait_s=%s validation_s=%.2f total_s=%.2f "
            "peak_rss_mib=%s job_dir_mib=%s "
            "parallel_jobs=%s max_concurrency=%s effective_max_concurrency=%s "
            "threads_per_job=%s effective_threads=%s partition_workers=%s "
            "cpu_cores=%s ram_avail_end_mib=%s disk_avail_end_gib=%s "
            "source_mib=%s target_mib=%s",
            self.job_id,
            self.upload_seconds,
            f"{self.queue_wait_seconds:.2f}" if self.queue_wait_seconds is not None else "n/a",
            self.validation_seconds or 0.0,
            self.total_seconds or 0.0,
            d.get("peak_rss_mib"),
            d.get("job_dir_mib"),
            self.parallel_jobs_running,
            self.max_concurrency,
            self.effective_max_concurrency,
            self.threads_per_job,
            self.effective_threads_per_job,
            self.partition_workers,
            self.end_snapshot.cpu_cores if self.end_snapshot else None,
            (self.end_snapshot.to_dict().get("available_ram_mib") if self.end_snapshot else None),
            (self.end_snapshot.to_dict().get("available_disk_gib") if self.end_snapshot else None),
            round(self.source_bytes / (1024**2), 1) if self.source_bytes else None,
            round(self.target_bytes / (1024**2), 1) if self.target_bytes else None,
        )
        logger.info("validation_run_metrics_detail %s", d)


def metrics_from_meta(job_dir: Path, meta: dict[str, object]) -> ValidationRunMetrics:
    ws = job_dir.parent
    metrics = ValidationRunMetrics(
        job_id=job_dir.name,
        upload_seconds=float(meta.get("upload_duration_seconds") or 0),
        start_snapshot=capture_system_snapshot(workspace=ws),
    )
    metrics.parallel_jobs_running = _int_or_none(meta.get("parallel_jobs_running"))
    metrics.max_concurrency = _int_or_none(meta.get("max_concurrency"))
    metrics.effective_max_concurrency = _int_or_none(meta.get("effective_max_concurrency"))
    metrics.queue_wait_seconds = _float_or_none(meta.get("queue_wait_seconds"))
    rp = meta.get("resource_policy")
    if isinstance(rp, dict):
        metrics.resource_policy = rp
        metrics.threads_per_job = _int_or_none(rp.get("threads_per_job"))
        metrics.effective_threads_per_job = _int_or_none(rp.get("effective_threads_per_job"))
        metrics.partition_workers = _int_or_none(rp.get("effective_threads_per_job"))
    for key, attr in (("source.csv", "source_bytes"), ("target.csv", "target_bytes")):
        p = job_dir / key
        if p.is_file():
            try:
                setattr(metrics, attr, p.stat().st_size)
            except OSError:
                pass
    return metrics


def _int_or_none(v: object) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _float_or_none(v: object) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
