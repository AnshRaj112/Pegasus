# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:32:35Z
# --- END GENERATED FILE METADATA ---

"""Pipeline stage timing and I/O metrics for performance profiling."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

StageProgressCallback = Callable[[dict[str, Any]], None]

_stage_metrics_log: Path | None = None


def configure_stage_metrics_log(path: Path | None) -> None:
    """Append each completed stage block to this file while validation runs."""
    global _stage_metrics_log
    _stage_metrics_log = path
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class PipelineIoStats:
    source_input_bytes: int = 0
    target_input_bytes: int = 0
    source_spill_bytes: int = 0
    target_spill_bytes: int = 0
    reconcile_spill_bytes_read: int = 0


@dataclass(slots=True)
class PipelineTimings:
    source_read_seconds: float = 0.0
    target_read_seconds: float = 0.0
    source_partition_seconds: float = 0.0
    target_partition_seconds: float = 0.0
    canonicalization_seconds: float = 0.0
    identity_generation_seconds: float = 0.0
    fingerprint_generation_seconds: float = 0.0
    partition_calculation_seconds: float = 0.0
    serialization_seconds: float = 0.0
    disk_write_seconds: float = 0.0
    disk_read_seconds: float = 0.0
    partition_reconciliation_seconds: float = 0.0
    column_comparison_seconds: float = 0.0
    report_generation_seconds: float = 0.0
    network_transfer_seconds: float = 0.0
    total_seconds: float = 0.0
    source_read_cpu_seconds: float = 0.0
    target_read_cpu_seconds: float = 0.0
    source_partition_cpu_seconds: float = 0.0
    target_partition_cpu_seconds: float = 0.0
    disk_read_cpu_seconds: float = 0.0
    partition_reconciliation_cpu_seconds: float = 0.0
    column_comparison_cpu_seconds: float = 0.0
    report_generation_cpu_seconds: float = 0.0
    total_cpu_seconds: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_read_seconds": round(self.source_read_seconds, 4),
            "target_read_seconds": round(self.target_read_seconds, 4),
            "canonicalization_seconds": round(self.canonicalization_seconds, 4),
            "identity_generation_seconds": round(self.identity_generation_seconds, 4),
            "fingerprint_generation_seconds": round(self.fingerprint_generation_seconds, 4),
            "partition_calculation_seconds": round(self.partition_calculation_seconds, 4),
            "serialization_seconds": round(self.serialization_seconds, 4),
            "disk_write_seconds": round(self.disk_write_seconds, 4),
            "disk_read_seconds": round(self.disk_read_seconds, 4),
            "partition_reconciliation_seconds": round(self.partition_reconciliation_seconds, 4),
            "column_comparison_seconds": round(self.column_comparison_seconds, 4),
            "report_generation_seconds": round(self.report_generation_seconds, 4),
            "network_transfer_seconds": round(self.network_transfer_seconds, 4),
            "total_seconds": round(self.total_seconds, 4),
            "source_read_cpu_seconds": round(self.source_read_cpu_seconds, 4),
            "target_read_cpu_seconds": round(self.target_read_cpu_seconds, 4),
            "source_partition_cpu_seconds": round(self.source_partition_cpu_seconds, 4),
            "target_partition_cpu_seconds": round(self.target_partition_cpu_seconds, 4),
            "disk_read_cpu_seconds": round(self.disk_read_cpu_seconds, 4),
            "partition_reconciliation_cpu_seconds": round(
                self.partition_reconciliation_cpu_seconds, 4
            ),
            "column_comparison_cpu_seconds": round(self.column_comparison_cpu_seconds, 4),
            "report_generation_cpu_seconds": round(self.report_generation_cpu_seconds, 4),
            "total_cpu_seconds": round(self.total_cpu_seconds, 4),
        }


def _cpu_field(wall_field: str) -> str | None:
    if not wall_field.endswith("_seconds"):
        return None
    return wall_field.replace("_seconds", "_cpu_seconds")


class StageTimer:
    """Accumulate wall and CPU time into a PipelineTimings field (thread-safe)."""

    __slots__ = ("_timings", "_field", "_cpu_field", "_start_wall", "_start_cpu")

    def __init__(self, timings: PipelineTimings, field_name: str) -> None:
        self._timings = timings
        self._field = field_name
        cpu_name = _cpu_field(field_name)
        self._cpu_field = (
            cpu_name
            if cpu_name and cpu_name in PipelineTimings.__dataclass_fields__
            else None
        )
        self._start_wall = 0.0
        self._start_cpu = 0.0

    def __enter__(self) -> StageTimer:
        self._start_wall = time.perf_counter()
        self._start_cpu = time.thread_time()
        return self

    def __exit__(self, *args: object) -> None:
        wall_elapsed = time.perf_counter() - self._start_wall
        cpu_elapsed = time.thread_time() - self._start_cpu
        with self._timings._lock:
            current = getattr(self._timings, self._field)
            setattr(self._timings, self._field, current + wall_elapsed)
            if self._cpu_field:
                cpu_current = getattr(self._timings, self._cpu_field)
                setattr(self._timings, self._cpu_field, cpu_current + cpu_elapsed)


@dataclass(frozen=True, slots=True)
class StageMetrics:
    name: str
    wall_seconds: float
    cpu_seconds: float
    bytes_read: int
    bytes_written: int


def spill_dir_bytes(work: Path, side: str) -> int:
    side_dir = work / side
    if not side_dir.is_dir():
        return 0
    return sum(p.stat().st_size for p in side_dir.glob("part_*.bin") if p.is_file())


def reconcile_spill_bytes_read(work: Path, partition_ids: set[int]) -> int:
    total = 0
    for pid in partition_ids:
        for side in ("source", "target"):
            path = work / side / f"part_{pid:05d}.bin"
            if path.is_file():
                total += path.stat().st_size
    return total


def adapter_input_bytes(adapter: object) -> int:
    getter = getattr(adapter, "get_bytes_read", None)
    if callable(getter):
        return int(getter())
    size_getter = getattr(adapter, "get_size_bytes", None)
    if callable(size_getter):
        return int(size_getter())
    return int(Path(getattr(adapter, "path")).stat().st_size)


def _partition_wall(timings: PipelineTimings, *, is_source: bool) -> float:
    total = timings.source_partition_seconds if is_source else timings.target_partition_seconds
    read = timings.source_read_seconds if is_source else timings.target_read_seconds
    return max(0.0, total - read)


def _partition_cpu(timings: PipelineTimings, *, is_source: bool) -> float:
    total = timings.source_partition_cpu_seconds if is_source else timings.target_partition_cpu_seconds
    read = timings.source_read_cpu_seconds if is_source else timings.target_read_cpu_seconds
    return max(0.0, total - read)


def _reconcile_wall(timings: PipelineTimings) -> float:
    if timings.disk_read_seconds > 0:
        return timings.disk_read_seconds
    return timings.partition_reconciliation_seconds + timings.column_comparison_seconds


def _reconcile_cpu(timings: PipelineTimings) -> float:
    if timings.disk_read_cpu_seconds > 0:
        return timings.disk_read_cpu_seconds
    return timings.partition_reconciliation_cpu_seconds + timings.column_comparison_cpu_seconds


def build_stage_metrics(
    timings: PipelineTimings,
    io: PipelineIoStats,
    *,
    report_wall_seconds: float | None = None,
    report_cpu_seconds: float | None = None,
) -> list[StageMetrics]:
    report_wall = (
        report_wall_seconds
        if report_wall_seconds is not None
        else timings.report_generation_seconds
    )
    report_cpu = (
        report_cpu_seconds
        if report_cpu_seconds is not None
        else timings.report_generation_cpu_seconds
    )
    return [
        StageMetrics(
            "Read Source",
            timings.source_read_seconds,
            timings.source_read_cpu_seconds,
            io.source_input_bytes,
            0,
        ),
        StageMetrics(
            "Partition Source",
            _partition_wall(timings, is_source=True),
            _partition_cpu(timings, is_source=True),
            0,
            io.source_spill_bytes,
        ),
        StageMetrics(
            "Read Target",
            timings.target_read_seconds,
            timings.target_read_cpu_seconds,
            io.target_input_bytes,
            0,
        ),
        StageMetrics(
            "Partition Target",
            _partition_wall(timings, is_source=False),
            _partition_cpu(timings, is_source=False),
            0,
            io.target_spill_bytes,
        ),
        StageMetrics(
            "Reconciliation",
            _reconcile_wall(timings),
            _reconcile_cpu(timings),
            io.reconcile_spill_bytes_read,
            0,
        ),
        StageMetrics(
            "Report",
            report_wall,
            report_cpu,
            0,
            0,
        ),
        StageMetrics(
            "Total",
            timings.total_seconds,
            timings.total_cpu_seconds,
            io.source_input_bytes + io.target_input_bytes + io.reconcile_spill_bytes_read,
            io.source_spill_bytes + io.target_spill_bytes,
        ),
    ]


def stage_metrics_to_dict(stages: list[StageMetrics]) -> list[dict[str, Any]]:
    return [
        {
            "name": s.name,
            "wall_seconds": round(s.wall_seconds, 4),
            "cpu_seconds": round(s.cpu_seconds, 4),
            "bytes_read": s.bytes_read,
            "bytes_written": s.bytes_written,
        }
        for s in stages
    ]


def _fmt_seconds(value: float) -> str:
    return f"{value:.4f} s"


def format_stage_report(stages: list[StageMetrics]) -> str:
    """Human-readable per-stage breakdown (seconds and bytes, no percentages)."""
    lines: list[str] = []
    for stage in stages:
        lines.append(f"{stage.name}:")
        lines.append(f"  Wall Time: {_fmt_seconds(stage.wall_seconds)}")
        lines.append(f"  CPU Time: {_fmt_seconds(stage.cpu_seconds)}")
        lines.append(f"  Bytes Read: {stage.bytes_read}")
        lines.append(f"  Bytes Written: {stage.bytes_written}")
        lines.append("")
    return "\n".join(lines).rstrip()


def stage_metric(stage: StageMetrics) -> dict[str, Any]:
    return stage_metrics_to_dict([stage])[0]


def publish_stage(
    stage: StageMetrics,
    *,
    progress_callback: StageProgressCallback | None = None,
) -> None:
    """Log and optionally push one completed stage while the pipeline is running."""
    block = format_stage_report([stage])
    logger.info("Pipeline stage complete\n%s", block)
    if _stage_metrics_log is not None:
        with _stage_metrics_log.open("a", encoding="utf-8") as fh:
            fh.write(block)
            fh.write("\n\n")
    if progress_callback is None:
        return
    progress_callback(
        {
            "phase": "stage",
            "message": f"{stage.name} complete",
            "stage": stage_metric(stage),
            "stage_report": block,
        }
    )


def publish_side_stages(
    timings: PipelineTimings,
    io: PipelineIoStats,
    *,
    is_source: bool,
    progress_callback: StageProgressCallback | None = None,
) -> None:
    """Emit Read/Partition metrics for one side after its partition work finishes."""
    names = ("Read Source", "Partition Source") if is_source else ("Read Target", "Partition Target")
    by_name = {s.name: s for s in build_stage_metrics(timings, io)}
    for name in names:
        stage = by_name.get(name)
        if stage is not None:
            publish_stage(stage, progress_callback=progress_callback)


def _timings_from_mapping(raw: dict[str, Any]) -> PipelineTimings:
    timings = PipelineTimings()
    for key, value in raw.items():
        if key in PipelineTimings.__dataclass_fields__ and key != "_lock":
            try:
                setattr(timings, key, float(value))
            except (TypeError, ValueError):
                pass
    return timings


def _io_from_mapping(raw: dict[str, Any]) -> PipelineIoStats:
    return PipelineIoStats(
        source_input_bytes=int(raw.get("source_input_bytes", 0)),
        target_input_bytes=int(raw.get("target_input_bytes", 0)),
        source_spill_bytes=int(raw.get("source_spill_bytes", 0)),
        target_spill_bytes=int(raw.get("target_spill_bytes", 0)),
        reconcile_spill_bytes_read=int(raw.get("reconcile_spill_bytes_read", 0)),
    )


def refresh_report_stage(
    extra_stats: dict[str, Any],
    *,
    wall_seconds: float,
    cpu_seconds: float,
) -> None:
    """Recompute stage report after external report generation."""
    timings = _timings_from_mapping(dict(extra_stats.get("timings") or {}))
    timings.report_generation_seconds = wall_seconds
    timings.report_generation_cpu_seconds = cpu_seconds
    io = _io_from_mapping(dict(extra_stats.get("io") or {}))
    attach_stage_report(extra_stats, timings, io)


def attach_stage_report(
    extra_stats: dict[str, Any],
    timings: PipelineTimings,
    io: PipelineIoStats,
    *,
    report_wall_seconds: float | None = None,
    report_cpu_seconds: float | None = None,
) -> None:
    stages = build_stage_metrics(
        timings,
        io,
        report_wall_seconds=report_wall_seconds,
        report_cpu_seconds=report_cpu_seconds,
    )
    extra_stats["timings"] = timings.to_dict()
    extra_stats["io"] = {
        "source_input_bytes": io.source_input_bytes,
        "target_input_bytes": io.target_input_bytes,
        "source_spill_bytes": io.source_spill_bytes,
        "target_spill_bytes": io.target_spill_bytes,
        "reconcile_spill_bytes_read": io.reconcile_spill_bytes_read,
    }
    extra_stats["stages"] = stage_metrics_to_dict(stages)
    extra_stats["stage_report"] = format_stage_report(stages)


def publish_final_stages(
    timings: PipelineTimings,
    io: PipelineIoStats,
    *,
    progress_callback: StageProgressCallback | None = None,
    report_wall_seconds: float | None = None,
    report_cpu_seconds: float | None = None,
    include_report: bool = True,
) -> list[StageMetrics]:
    """Log Total (and Report when applicable) at end of the run."""
    stages = build_stage_metrics(
        timings,
        io,
        report_wall_seconds=report_wall_seconds,
        report_cpu_seconds=report_cpu_seconds,
    )
    for stage in stages:
        if stage.name == "Total" or (include_report and stage.name == "Report"):
            publish_stage(stage, progress_callback=progress_callback)
    return stages
