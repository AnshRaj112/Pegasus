# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T14:52:27Z
# --- END GENERATED FILE METADATA ---

"""Lifecycle profiler aggregates stages and writes artifacts."""

from __future__ import annotations

import time
from pathlib import Path

from pegasus.validation.lifecycle_profiler import LifecycleProfiler, lifecycle_job, lifecycle_span


def test_lifecycle_profiler_writes_report(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    with lifecycle_job(job_dir) as prof:
        prof.mark_http_request_start()
        time.sleep(0.01)
        prof.mark_job_enqueued()
        prof.mark_worker_started()
        with lifecycle_span("GCS Prefetch"):
            time.sleep(0.01)
        prof.ingest_pipeline_stages(
            [
                {
                    "name": "Total",
                    "wall_seconds": 8.18,
                    "cpu_seconds": 2.0,
                    "bytes_read": 100,
                    "bytes_written": 50,
                }
            ]
        )
        prof.mark_worker_finished()
        prof.write_artifacts()

    assert (job_dir / "lifecycle_timings.json").is_file()
    assert (job_dir / "lifecycle_report.md").is_file()
    summary = prof.summarize()
    assert summary["totals"]["pipeline_total_wall_seconds"] == 8.18
