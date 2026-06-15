# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:08:54Z
# --- END GENERATED FILE METADATA ---

"""Resource profiler snapshot and merge helpers."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.resource_profiler import (
    JobResourceProfiler,
    capture_resource_snapshot,
    format_resource_profile_report,
    log_resource_snapshot_summary,
    merge_resource_profile,
    write_resource_profile_artifacts,
)


def test_capture_resource_snapshot_has_memory_and_disk() -> None:
    snap = capture_resource_snapshot(label="test")
    assert snap["label"] == "test"
    assert "memory" in snap
    assert "disk" in snap
    assert "cpu" in snap
    assert snap["memory"]["total_bytes"] > 0
    assert snap["disk"]["total_bytes"] > 0


def test_job_resource_profiler_tracks_before_after(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    (job_dir / "meta.json").write_text("{}", encoding="utf-8")

    profiler = JobResourceProfiler(job_dir=job_dir, sample_interval_seconds=0.0)
    before = profiler.capture_before()
    assert before["label"] == "before"
    profiler.maybe_capture_during(force=True)
    after = profiler.capture_after()
    assert after["label"] == "after"
    payload = profiler.to_dict()
    assert payload["before"] is not None
    assert payload["after"] is not None
    assert payload["during_samples"] == 1


def test_format_resource_profile_report_includes_sections() -> None:
    report = format_resource_profile_report(
        {
            "before": {
                "memory": {"available_gib": 4.0, "used_gib": 11.5, "process_rss_mib": 180.3},
                "disk": {"available_gib": 187.8, "used_gib": 12.0, "job_workspace_mib": 0.0},
                "cpu": {"process_percent": None, "system_percent": None, "cores": 8},
            },
            "latest": {
                "memory": {"available_gib": 3.8, "used_gib": 11.6, "process_rss_mib": 197.0},
                "disk": {"available_gib": 187.8, "used_gib": 12.0, "job_workspace_mib": 2.9},
                "cpu": {"process_percent": 17.7, "system_percent": 57.2, "cores": 8},
            },
            "after": {
                "memory": {"available_gib": 4.1, "used_gib": 11.4, "process_rss_mib": 120.0},
                "disk": {"available_gib": 187.7, "used_gib": 12.1, "job_workspace_mib": 3.1},
                "cpu": {"process_percent": 5.0, "system_percent": 12.0, "cores": 8},
            },
            "peak": {
                "process_rss_mib": 197.0,
                "process_rss_bytes": 206372864,
                "job_workspace_mib": 2.9,
                "process_percent": 17.7,
            },
            "during_samples": 3,
        }
    )
    assert "Before validation" in report
    assert "During validation" in report
    assert "After validation" in report
    assert "Peak process RSS" in report


def test_write_resource_profile_artifacts(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    write_resource_profile_artifacts(
        job_dir,
        {
            "before": {
                "memory": {"available_gib": 4.0, "used_gib": 11.5, "process_rss_mib": 180.3},
                "disk": {"available_gib": 187.8, "used_gib": 12.0, "job_workspace_mib": 0.0},
                "cpu": {"cores": 8},
            },
        },
    )
    assert (job_dir / "resource_profile_report.md").is_file()


def test_log_resource_snapshot_summary_does_not_raise() -> None:
    log_resource_snapshot_summary(
        {
            "memory": {"available_gib": 4.0, "used_gib": 11.5, "process_rss_mib": 180.3},
            "disk": {"available_gib": 187.8, "job_workspace_mib": 2.9},
            "cpu": {"process_percent": 12.5, "system_percent": 40.0, "cores": 8},
        },
        phase="before",
        job_id="test-job",
    )


def test_merge_resource_profile_appends_during_samples() -> None:
    merged = merge_resource_profile(
        {"before": {"label": "before"}, "during": [{"label": "a"}]},
        {"during": [{"label": "b"}], "peak": {"process_rss_bytes": 1024}},
    )
    assert len(merged["during"]) == 2
    assert merged["during_samples"] == 2
    assert merged["latest"]["label"] == "b"
    assert merged["peak"]["process_rss_bytes"] == 1024
