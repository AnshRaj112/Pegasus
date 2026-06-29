# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-28T11:56:30Z
# --- END GENERATED FILE METADATA ---

"""Per-job memory, disk, and CPU footprint snapshots (before / during / after)."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from pegasus.services.resource_advisor import (
    _available_disk_bytes,
    _available_ram_bytes,
    _swap_pressure,
    _total_disk_bytes,
    _total_ram_bytes,
)

_CLOCK_TICKS = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def _read_proc_self_rss_bytes() -> int | None:
    try:
        text = Path("/proc/self/status").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def _read_proc_self_cpu_ticks() -> tuple[int, int] | None:
    try:
        parts = Path("/proc/self/stat").read_text(encoding="utf-8").split()
        utime = int(parts[13])
        stime = int(parts[14])
        return utime, stime
    except (OSError, ValueError, IndexError):
        return None


def _read_system_cpu_sample() -> tuple[int, int] | None:
    try:
        line = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0]
        fields = [int(x) for x in line.split()[1:]]
        idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
        total = sum(fields)
        return idle, total
    except (OSError, ValueError, IndexError):
        return None


def _job_workspace_bytes(job_dir: Path | None) -> int:
    if job_dir is None or not job_dir.is_dir():
        return 0
    total = 0
    try:
        for path in job_dir.rglob("*"):
            if path.is_file():
                try:
                    total += path.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def capture_resource_snapshot(
    *,
    job_dir: Path | None = None,
    label: str = "snapshot",
    prev_system_cpu: tuple[int, int] | None = None,
    prev_process_cpu: tuple[int, int] | None = None,
    elapsed_wall_seconds: float | None = None,
) -> dict[str, Any]:
    """Capture a point-in-time resource snapshot for API / status.json."""
    workspace = job_dir.resolve() if job_dir is not None else None
    total_ram = _total_ram_bytes()
    available_ram = _available_ram_bytes()
    total_disk = _total_disk_bytes(workspace)
    available_disk = _available_disk_bytes(workspace)
    used_ram = max(0, total_ram - available_ram)
    used_disk = max(0, total_disk - available_disk)
    job_disk_bytes = _job_workspace_bytes(workspace)
    rss_bytes = _read_proc_self_rss_bytes()
    cpu_cores = max(1, os.cpu_count() or 1)

    system_cpu_percent: float | None = None
    process_cpu_percent: float | None = None
    system_sample = _read_system_cpu_sample()
    process_sample = _read_proc_self_cpu_ticks()

    if (
        prev_system_cpu is not None
        and system_sample is not None
        and elapsed_wall_seconds
        and elapsed_wall_seconds > 0
    ):
        idle_delta = system_sample[0] - prev_system_cpu[0]
        total_delta = system_sample[1] - prev_system_cpu[1]
        if total_delta > 0:
            system_cpu_percent = round(max(0.0, min(100.0, (1.0 - idle_delta / total_delta) * 100.0)), 2)

    if (
        prev_process_cpu is not None
        and process_sample is not None
        and elapsed_wall_seconds
        and elapsed_wall_seconds > 0
    ):
        proc_delta = (process_sample[0] - prev_process_cpu[0]) + (process_sample[1] - prev_process_cpu[1])
        proc_seconds = proc_delta / float(_CLOCK_TICKS)
        process_cpu_percent = round(
            max(0.0, min(100.0 * cpu_cores, (proc_seconds / elapsed_wall_seconds) * 100.0)),
            2,
        )

    return {
        "label": label,
        "captured_at_epoch_s": time.time(),
        "memory": {
            "total_bytes": total_ram,
            "available_bytes": available_ram,
            "used_bytes": used_ram,
            "total_gib": round(total_ram / 1024**3, 2),
            "available_gib": round(available_ram / 1024**3, 2),
            "used_gib": round(used_ram / 1024**3, 2),
            "process_rss_bytes": rss_bytes,
            "process_rss_mib": round(rss_bytes / 1024**2, 1) if rss_bytes is not None else None,
        },
        "disk": {
            "total_bytes": total_disk,
            "available_bytes": available_disk,
            "used_bytes": used_disk,
            "total_gib": round(total_disk / 1024**3, 2),
            "available_gib": round(available_disk / 1024**3, 2),
            "used_gib": round(used_disk / 1024**3, 2),
            "job_workspace_bytes": job_disk_bytes,
            "job_workspace_mib": round(job_disk_bytes / 1024**2, 1),
        },
        "cpu": {
            "cores": cpu_cores,
            "system_percent": system_cpu_percent,
            "process_percent": process_cpu_percent,
        },
        "swap_pressure": _swap_pressure(),
        "_system_cpu_sample": system_sample,
        "_process_cpu_sample": process_sample,
    }


def _public_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in raw.items() if not str(k).startswith("_")}


@dataclass
class JobResourceProfiler:
    """Tracks before / during / after resource footprints for one validation job."""

    job_dir: Path
    sample_interval_seconds: float = 5.0
    max_during_samples: int = 120
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    during: list[dict[str, Any]] = field(default_factory=list)
    peak: dict[str, Any] = field(default_factory=dict)
    _last_sample_at: float = 0.0
    _started_at: float = field(default_factory=time.time)
    _baseline_system_cpu: tuple[int, int] | None = None
    _baseline_process_cpu: tuple[int, int] | None = None
    _last_system_cpu: tuple[int, int] | None = None
    _last_process_cpu: tuple[int, int] | None = None

    def capture_before(self) -> dict[str, Any]:
        snap = capture_resource_snapshot(job_dir=self.job_dir, label="before")
        self.before = _public_snapshot(snap)
        self._baseline_system_cpu = snap.get("_system_cpu_sample")
        self._baseline_process_cpu = snap.get("_process_cpu_sample")
        self._last_system_cpu = self._baseline_system_cpu
        self._last_process_cpu = self._baseline_process_cpu
        self._started_at = time.time()
        self._update_peak(self.before)
        return self.before

    def maybe_capture_during(self, *, force: bool = False) -> dict[str, Any] | None:
        now = time.time()
        if not force and now - self._last_sample_at < self.sample_interval_seconds:
            return None
        elapsed = max(0.001, now - self._last_sample_at if self._last_sample_at else now - self._started_at)
        snap = capture_resource_snapshot(
            job_dir=self.job_dir,
            label="during",
            prev_system_cpu=self._last_system_cpu,
            prev_process_cpu=self._last_process_cpu,
            elapsed_wall_seconds=elapsed,
        )
        public = _public_snapshot(snap)
        self.during.append(public)
        if len(self.during) > self.max_during_samples:
            self.during = self.during[-self.max_during_samples :]
        self._last_sample_at = now
        self._last_system_cpu = snap.get("_system_cpu_sample")
        self._last_process_cpu = snap.get("_process_cpu_sample")
        self._update_peak(public)
        return public

    def capture_after(self) -> dict[str, Any]:
        elapsed = max(0.001, time.time() - (self._last_sample_at or self._started_at))
        snap = capture_resource_snapshot(
            job_dir=self.job_dir,
            label="after",
            prev_system_cpu=self._last_system_cpu,
            prev_process_cpu=self._last_process_cpu,
            elapsed_wall_seconds=elapsed,
        )
        self.after = _public_snapshot(snap)
        self._update_peak(self.after)
        return self.after

    def _update_peak(self, snap: dict[str, Any]) -> None:
        mem = snap.get("memory") if isinstance(snap.get("memory"), dict) else {}
        disk = snap.get("disk") if isinstance(snap.get("disk"), dict) else {}
        cpu = snap.get("cpu") if isinstance(snap.get("cpu"), dict) else {}
        rss = mem.get("process_rss_bytes")
        if isinstance(rss, int):
            prev = self.peak.get("process_rss_bytes")
            if not isinstance(prev, int) or rss > prev:
                self.peak["process_rss_bytes"] = rss
                self.peak["process_rss_mib"] = mem.get("process_rss_mib")
        job_disk = disk.get("job_workspace_bytes")
        if isinstance(job_disk, int):
            prev_disk = self.peak.get("job_workspace_bytes")
            if not isinstance(prev_disk, int) or job_disk > prev_disk:
                self.peak["job_workspace_bytes"] = job_disk
                self.peak["job_workspace_mib"] = disk.get("job_workspace_mib")
        for key in ("system_percent", "process_percent"):
            value = cpu.get(key)
            if isinstance(value, (int, float)):
                prev_cpu = self.peak.get(key)
                if not isinstance(prev_cpu, (int, float)) or value > prev_cpu:
                    self.peak[key] = value

    def to_dict(self) -> dict[str, Any]:
        latest = self.during[-1] if self.during else self.after or self.before
        return {
            "before": self.before,
            "during_samples": len(self.during),
            "latest": latest,
            "after": self.after,
            "peak": self.peak,
        }


def _snapshot_report_lines(snap: dict[str, Any] | None, *, heading: str) -> list[str]:
    if not snap:
        return []
    mem = snap.get("memory") if isinstance(snap.get("memory"), dict) else {}
    disk = snap.get("disk") if isinstance(snap.get("disk"), dict) else {}
    cpu = snap.get("cpu") if isinstance(snap.get("cpu"), dict) else {}
    lines = [f"### {heading}"]
    lines.append(
        f"- Memory: available={mem.get('available_gib')} GiB used={mem.get('used_gib')} GiB "
        f"process_rss={mem.get('process_rss_mib')} MiB"
    )
    lines.append(
        f"- Disk: free={disk.get('available_gib')} GiB used={disk.get('used_gib')} GiB "
        f"job_workspace={disk.get('job_workspace_mib')} MiB"
    )
    proc_cpu = cpu.get("process_percent")
    sys_cpu = cpu.get("system_percent")
    lines.append(
        f"- CPU: process={proc_cpu if proc_cpu is not None else 'n/a'}% "
        f"system={sys_cpu if sys_cpu is not None else 'n/a'}% cores={cpu.get('cores')}"
    )
    if snap.get("swap_pressure") is not None:
        lines.append(f"- Swap pressure: {snap.get('swap_pressure')}")
    lines.append("")
    return lines


def log_resource_snapshot_summary(
    snap: dict[str, Any] | None,
    *,
    phase: str,
    job_id: str | None = None,
) -> None:
    """Emit a one-line memory / disk / CPU summary to worker logs."""
    if not snap:
        return
    mem = snap.get("memory") if isinstance(snap.get("memory"), dict) else {}
    disk = snap.get("disk") if isinstance(snap.get("disk"), dict) else {}
    cpu = snap.get("cpu") if isinstance(snap.get("cpu"), dict) else {}
    prefix = f"job={job_id} " if job_id else ""
    logger.info(
        "%sresource [%s]: mem avail=%s GiB used=%s GiB rss=%s MiB | "
        "disk free=%s GiB job_ws=%s MiB | cpu proc=%s%% sys=%s%% cores=%s",
        prefix,
        phase,
        mem.get("available_gib"),
        mem.get("used_gib"),
        mem.get("process_rss_mib"),
        disk.get("available_gib"),
        disk.get("job_workspace_mib"),
        cpu.get("process_percent") if cpu.get("process_percent") is not None else "n/a",
        cpu.get("system_percent") if cpu.get("system_percent") is not None else "n/a",
        cpu.get("cores"),
    )


def format_resource_profile_report(profile: dict[str, Any]) -> str:
    """Human-readable before / during / after resource footprint report."""
    during = profile.get("during") if isinstance(profile.get("during"), list) else []
    latest = profile.get("latest") if isinstance(profile.get("latest"), dict) else None
    if latest is None and during:
        latest = during[-1] if isinstance(during[-1], dict) else None
    lines = ["# Validation resource footprint", ""]
    lines.extend(_snapshot_report_lines(profile.get("before"), heading="Before validation"))
    lines.extend(_snapshot_report_lines(latest, heading="During validation (latest sample)"))
    lines.extend(_snapshot_report_lines(profile.get("after"), heading="After validation"))
    peak = profile.get("peak") if isinstance(profile.get("peak"), dict) else {}
    if peak:
        lines.append("### Peak")
        lines.append(
            f"- Peak process RSS: {peak.get('process_rss_mib')} MiB "
            f"({peak.get('process_rss_bytes')} bytes)"
        )
        lines.append(
            f"- Peak job workspace: {peak.get('job_workspace_mib')} MiB "
            f"({peak.get('job_workspace_bytes')} bytes)"
        )
        lines.append(
            f"- Peak CPU: process={peak.get('process_percent')}% system={peak.get('system_percent')}%"
        )
        lines.append(f"- During samples collected: {profile.get('during_samples', len(during))}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_resource_profile_artifacts(job_dir: Path, profile: dict[str, Any]) -> str:
    """Write resource_profile_report.md and emit the same text to worker logs."""
    report = format_resource_profile_report(profile)
    path = job_dir / "resource_profile_report.md"
    path.write_text(report, encoding="utf-8")
    logger.info("Resource footprint report for %s\n%s", job_dir.name, report.rstrip())
    return report


def merge_resource_profile(existing: dict[str, Any] | None, update: dict[str, Any]) -> dict[str, Any]:
    """Merge profiler state into an existing status.json resource_profile blob."""
    base = dict(existing or {})
    for key, value in update.items():
        if value is None:
            continue
        if key == "during" and isinstance(value, list):
            prior = base.get("during")
            if isinstance(prior, list):
                base["during"] = prior + value
            else:
                base["during"] = value
            base["during_samples"] = len(base["during"])
            continue
        base[key] = value
    if isinstance(base.get("during"), list):
        base["during_samples"] = len(base["during"])
        if base["during"]:
            base["latest"] = base["during"][-1]
    return base
