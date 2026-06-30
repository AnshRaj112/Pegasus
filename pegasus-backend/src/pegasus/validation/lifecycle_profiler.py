# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T08:29:07Z
# --- END GENERATED FILE METADATA ---

"""End-to-end validation request lifecycle profiling (wall + CPU + I/O)."""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from pegasus.core.json_util import dumps_bytes

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_active: LifecycleProfiler | None = None


@dataclass(slots=True)
class LifecycleStageRecord:
    name: str
    wall_seconds: float = 0.0
    cpu_seconds: float = 0.0
    bytes_read: int = 0
    bytes_written: int = 0
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "wall_seconds": round(self.wall_seconds, 4),
            "cpu_seconds": round(self.cpu_seconds, 4),
            "bytes_read": self.bytes_read,
            "bytes_written": self.bytes_written,
        }
        if self.detail:
            out["detail"] = self.detail
        return out


@dataclass
class LifecycleProfiler:
    """Accumulates per-stage metrics for one validation job."""

    job_dir: Path | None = None
    http_request_start_epoch_s: float | None = None
    job_enqueued_epoch_s: float | None = None
    worker_started_epoch_s: float | None = None
    validation_started_epoch_s: float | None = None
    worker_finished_epoch_s: float | None = None
    http_response_epoch_s: float | None = None
    stages: dict[str, LifecycleStageRecord] = field(default_factory=dict)
    _stage_lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def set_job_dir(self, path: Path) -> None:
        self.job_dir = path.resolve()

    def mark_http_request_start(self) -> None:
        self.http_request_start_epoch_s = time.time()

    def mark_job_enqueued(self) -> None:
        self.job_enqueued_epoch_s = time.time()

    def mark_worker_started(self) -> None:
        self.worker_started_epoch_s = time.time()

    def mark_validation_started(self) -> None:
        self.validation_started_epoch_s = time.time()

    def mark_worker_finished(self) -> None:
        self.worker_finished_epoch_s = time.time()

    def mark_http_response(self) -> None:
        self.http_response_epoch_s = time.time()

    def record(
        self,
        name: str,
        *,
        wall_seconds: float = 0.0,
        cpu_seconds: float = 0.0,
        bytes_read: int = 0,
        bytes_written: int = 0,
        detail: str | None = None,
        accumulate: bool = True,
    ) -> None:
        with self._stage_lock:
            existing = self.stages.get(name)
            if existing is None:
                self.stages[name] = LifecycleStageRecord(
                    name=name,
                    wall_seconds=wall_seconds,
                    cpu_seconds=cpu_seconds,
                    bytes_read=bytes_read,
                    bytes_written=bytes_written,
                    detail=detail,
                )
                return
            if accumulate:
                existing.wall_seconds += wall_seconds
                existing.cpu_seconds += cpu_seconds
                existing.bytes_read += bytes_read
                existing.bytes_written += bytes_written
            else:
                existing.wall_seconds = wall_seconds
                existing.cpu_seconds = cpu_seconds
                existing.bytes_read = bytes_read
                existing.bytes_written = bytes_written
            if detail:
                existing.detail = detail

    @contextmanager
    def span(
        self,
        name: str,
        *,
        bytes_read: int = 0,
        bytes_written: int = 0,
        detail: str | None = None,
    ) -> Iterator[None]:
        wall_start = time.perf_counter()
        cpu_start = time.thread_time()
        try:
            yield
        finally:
            self.record(
                name,
                wall_seconds=time.perf_counter() - wall_start,
                cpu_seconds=time.thread_time() - cpu_start,
                bytes_read=bytes_read,
                bytes_written=bytes_written,
                detail=detail,
            )

    def ingest_pipeline_stages(self, stages: list[dict[str, Any]]) -> None:
        """Copy spill-path stage metrics from pipeline timing."""
        mapping = {
            "Read Source": "Read Source",
            "Partition Source": "Partition Source",
            "Read Target": "Read Target",
            "Partition Target": "Partition Target",
            "Reconciliation": "Reconciliation",
            "Report": "Report Generation",
            "Total": "Pipeline Total",
        }
        for raw in stages:
            src_name = str(raw.get("name") or "")
            dest = mapping.get(src_name)
            if not dest:
                continue
            self.record(
                dest,
                wall_seconds=float(raw.get("wall_seconds") or 0),
                cpu_seconds=float(raw.get("cpu_seconds") or 0),
                bytes_read=int(raw.get("bytes_read") or 0),
                bytes_written=int(raw.get("bytes_written") or 0),
                accumulate=False,
            )

    def _derived_gaps(self) -> list[LifecycleStageRecord]:
        """Synthetic stages from epoch markers (queue wait, poll-to-response, etc.)."""
        derived: list[LifecycleStageRecord] = []

        def _gap(name: str, start: float | None, end: float | None) -> None:
            if start is None or end is None:
                return
            wall = max(0.0, end - start)
            if wall <= 0:
                return
            derived.append(LifecycleStageRecord(name=name, wall_seconds=wall))

        _gap("Job Creation", self.http_request_start_epoch_s, self.job_enqueued_epoch_s)
        _gap("Queue Wait", self.job_enqueued_epoch_s, self.worker_started_epoch_s)
        _gap(
            "Worker Init (pre-validation)",
            self.worker_started_epoch_s,
            self.validation_started_epoch_s,
        )
        _gap(
            "Post-Validation Finalization",
            self.worker_finished_epoch_s,
            self.http_response_epoch_s,
        )
        if self.http_request_start_epoch_s and self.http_response_epoch_s:
            derived.append(
                LifecycleStageRecord(
                    name="HTTP Request → Response",
                    wall_seconds=max(
                        0.0, self.http_response_epoch_s - self.http_request_start_epoch_s
                    ),
                )
            )
        if self.worker_started_epoch_s and self.worker_finished_epoch_s:
            derived.append(
                LifecycleStageRecord(
                    name="Worker Total",
                    wall_seconds=max(
                        0.0, self.worker_finished_epoch_s - self.worker_started_epoch_s
                    ),
                )
            )
        return derived

    def ordered_report(self) -> list[LifecycleStageRecord]:
        """Canonical stage order for 100% wall-time accounting."""
        order = [
            "HTTP Request Start",
            "Job Creation",
            "Queue Wait",
            "Worker Init (pre-validation)",
            "Validation Start",
            "GCS Prefetch",
            "Schema And Planning",
            "Pipeline Precheck",
            "In-Memory Fast Path",
            "Polars Direct Fast Path",
            "Read Source",
            "Partition Source",
            "Read Target",
            "Partition Target",
            "Reconciliation",
            "Mismatch Export",
            "Report Generation",
            "Pipeline Total",
            "Result Serialization",
            "Database Updates",
            "GCS Uploads",
            "Job Finalization",
            "Worker Total",
            "Post-Validation Finalization",
            "HTTP Request → Response",
        ]
        merged: dict[str, LifecycleStageRecord] = {}
        for rec in self._derived_gaps():
            merged[rec.name] = rec
        for name, rec in self.stages.items():
            merged[name] = rec

        out: list[LifecycleStageRecord] = []
        seen: set[str] = set()
        for name in order:
            rec = merged.get(name)
            if rec is not None:
                out.append(rec)
                seen.add(name)
        for name, rec in sorted(merged.items()):
            if name not in seen:
                out.append(rec)
        return out

    def summarize(self) -> dict[str, Any]:
        stages = self.ordered_report()
        pipeline_total = self.stages.get("Pipeline Total")
        worker_total_rec = next((s for s in self._derived_gaps() if s.name == "Worker Total"), None)
        http_total_rec = next(
            (s for s in self._derived_gaps() if s.name == "HTTP Request → Response"), None
        )
        rollup_names = {
            "HTTP Request → Response",
            "Worker Total",
            "Pipeline Total",
            "Job Creation",
            "Queue Wait",
            "Worker Init (pre-validation)",
            "Post-Validation Finalization",
        }
        accounted = sum(s.wall_seconds for s in stages if s.name not in rollup_names)
        worker_wall = worker_total_rec.wall_seconds if worker_total_rec else 0.0
        pipeline_wall = pipeline_total.wall_seconds if pipeline_total else 0.0
        unaccounted_vs_worker = max(0.0, worker_wall - accounted) if worker_wall else 0.0
        unaccounted_vs_pipeline = max(0.0, worker_wall - pipeline_wall) if worker_wall else 0.0
        pre_pipeline = sum(
            s.wall_seconds
            for s in stages
            if s.name
            in {
                "GCS Prefetch",
                "Schema And Planning",
                "Pipeline Precheck",
                "In-Memory Fast Path",
                "Polars Direct Fast Path",
            }
        )

        return {
            "epochs": {
                "http_request_start_epoch_s": self.http_request_start_epoch_s,
                "job_enqueued_epoch_s": self.job_enqueued_epoch_s,
                "worker_started_epoch_s": self.worker_started_epoch_s,
                "validation_started_epoch_s": self.validation_started_epoch_s,
                "worker_finished_epoch_s": self.worker_finished_epoch_s,
                "http_response_epoch_s": self.http_response_epoch_s,
            },
            "stages": [s.to_dict() for s in stages],
            "stage_report": format_lifecycle_report(stages),
            "totals": {
                "pipeline_total_wall_seconds": pipeline_wall,
                "worker_total_wall_seconds": worker_wall,
                "http_total_wall_seconds": http_total_rec.wall_seconds if http_total_rec else 0.0,
                "accounted_stage_wall_seconds": round(accounted, 4),
                "pre_pipeline_wall_seconds": round(pre_pipeline, 4),
                "unaccounted_vs_worker_seconds": round(unaccounted_vs_worker, 4),
                "unaccounted_vs_pipeline_seconds": round(unaccounted_vs_pipeline, 4),
            },
        }

    def write_artifacts(self) -> None:
        if self.job_dir is None:
            return
        summary = self.summarize()
        path = self.job_dir / "lifecycle_timings.json"
        path.write_bytes(dumps_bytes(summary, indent=True))
        report_path = self.job_dir / "lifecycle_report.md"
        report_path.write_text(
            "# Validation lifecycle timings\n\n" + summary["stage_report"] + "\n",
            encoding="utf-8",
        )
        top_stages = sorted(
            (s for s in self.ordered_report() if s.wall_seconds >= 0.05),
            key=lambda s: s.wall_seconds,
            reverse=True,
        )[:5]
        stage_hint = ", ".join(f"{s.name}={s.wall_seconds:.2f}s" for s in top_stages)
        logger.info(
            "Lifecycle profile worker_total=%.2fs pipeline_total=%.2fs "
            "pre_pipeline=%.2fs worker_overhead_vs_pipeline=%.2fs (%s)",
            summary["totals"]["worker_total_wall_seconds"],
            summary["totals"]["pipeline_total_wall_seconds"],
            summary["totals"]["pre_pipeline_wall_seconds"],
            summary["totals"]["unaccounted_vs_pipeline_seconds"],
            stage_hint or "no staged detail",
        )


def format_lifecycle_report(stages: list[LifecycleStageRecord]) -> str:
    lines: list[str] = []
    for stage in stages:
        lines.append(f"### {stage.name}")
        lines.append(f"- Wall Time: {stage.wall_seconds:.4f} s")
        lines.append(f"- CPU Time: {stage.cpu_seconds:.4f} s")
        lines.append(f"- Bytes Read: {stage.bytes_read}")
        lines.append(f"- Bytes Written: {stage.bytes_written}")
        if stage.detail:
            lines.append(f"- Detail: {stage.detail}")
        lines.append("")
    return "\n".join(lines).rstrip()


def set_active_profiler(profiler: LifecycleProfiler | None) -> LifecycleProfiler | None:
    global _active
    with _lock:
        prev = _active
        _active = profiler
    return prev


def get_active_profiler() -> LifecycleProfiler | None:
    with _lock:
        return _active


@contextmanager
def lifecycle_job(job_dir: Path) -> Iterator[LifecycleProfiler]:
    profiler = LifecycleProfiler(job_dir=job_dir.resolve())
    prev = set_active_profiler(profiler)
    try:
        yield profiler
    finally:
        set_active_profiler(prev)


@contextmanager
def lifecycle_span(
    name: str,
    *,
    bytes_read: int = 0,
    bytes_written: int = 0,
    detail: str | None = None,
) -> Iterator[None]:
    """No-op when no profiler is active."""
    profiler = get_active_profiler()
    if profiler is None:
        yield
        return
    with profiler.span(name, bytes_read=bytes_read, bytes_written=bytes_written, detail=detail):
        yield
