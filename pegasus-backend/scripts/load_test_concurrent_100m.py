#!/usr/bin/env python3
"""Submit N local 100M-row validations at once; measure queue + per-job timings."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pegasus-backend" / "src"))

from pegasus.core.config import Settings, get_settings
from pegasus.core.json_util import dumps_bytes
from pegasus.services.job_resource_meta import local_path_size_bytes, stamp_resource_sizes
from pegasus.services.validation_job_queue import JobState, ValidationJobQueue, reset_validation_queue
import tempfile


def validation_jobs_root(settings: Settings) -> Path:
    raw = settings.validation_jobs_directory
    if raw:
        root = Path(raw).expanduser()
    else:
        root = Path(tempfile.gettempdir()) / "pegasus_validation_jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


SOURCE = REPO / "test-data/generated-100m-12cols/source.csv"
TARGET = REPO / "test-data/generated-100m-12cols/target.csv"


def _create_job_dir(settings: Settings, job_id: uuid.UUID) -> Path:
    job_dir = validation_jobs_root(settings) / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)
    src_bytes = local_path_size_bytes(SOURCE)
    tgt_bytes = local_path_size_bytes(TARGET)
    meta = {
        "uid_column": "id",
        "delimiter": "||",
        "column_mappings": [],
        "validate_header_formats": False,
        "validate_footers": False,
        "footer_trailing_rows": 1,
        "has_header": True,
        "header_leading_rows": 0,
        "run_id": None,
        "source_filename": SOURCE.name,
        "target_filename": TARGET.name,
        "file_format": "csv",
        "test_mode": "full",
        "source_path": str(SOURCE.resolve()),
        "target_path": str(TARGET.resolve()),
    }
    stamp_resource_sizes(meta, source_bytes=src_bytes, target_bytes=tgt_bytes, column_count=12)
    (job_dir / "meta.json").write_bytes(dumps_bytes(meta, indent=True))
    (job_dir / "status.json").write_bytes(
        dumps_bytes(
            {
                "status": "queued",
                "phase": "queued",
                "message": "load test enqueue",
                "progress": {"enqueued_at_epoch_s": time.time()},
            },
            indent=True,
        )
    )
    return job_dir


async def _wait_for_jobs(queue: ValidationJobQueue, job_ids: list[uuid.UUID]) -> list[dict]:
    records: dict[uuid.UUID, dict] = {
        jid: {"job_id": str(jid), "enqueued_at": None, "started_at": None, "finished_at": None, "state": None}
        for jid in job_ids
    }
    t_submit = time.time()
    for jid in job_ids:
        records[jid]["enqueued_at"] = t_submit

    loop = asyncio.get_running_loop()
    queue.start_drain_loop(loop)

    while True:
        all_done = True
        with queue._lock:  # noqa: SLF001
            for jid in job_ids:
                job = queue._all_jobs.get(jid)  # noqa: SLF001
                if job is None:
                    continue
                rec = records[jid]
                rec["state"] = job.state.value
                if job.started_at and rec["started_at"] is None:
                    rec["started_at"] = job.started_at
                if job.finished_at:
                    rec["finished_at"] = job.finished_at
                if job.state not in (JobState.COMPLETED, JobState.FAILED):
                    all_done = False
        if all_done:
            break
        await asyncio.sleep(2.0)

    await queue.shutdown(wait=False)
    return [records[jid] for jid in job_ids]


def _validation_seconds(job_dir: Path) -> float | None:
    result_path = job_dir / "result.json"
    if not result_path.is_file():
        return None
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
        durations = data.get("durations") or {}
        val = durations.get("validation_seconds")
        return float(val) if val is not None else None
    except (OSError, ValueError, TypeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=5, help="Number of concurrent submissions")
    parser.add_argument("--auto-tune", action="store_true", help="Enable resource auto-tune (default off for predictable start)")
    args = parser.parse_args()

    if not SOURCE.is_file() or not TARGET.is_file():
        print(json.dumps({"error": "100m-12cols fixtures missing", "source": str(SOURCE)}))
        sys.exit(1)

    reset_validation_queue()
    get_settings.cache_clear()

    settings = Settings(
        validation_allow_local_paths=True,
        validation_enable_in_memory_reconcile=False,
        validation_auto_tune_enabled=args.auto_tune,
        validation_max_concurrency=10,
        validation_worker_pool_size=0,
        validation_partition_reconcile_workers=0,
        validation_enable_content_digest_precheck=False,
        validation_cleanup_workspace_on_complete=True,
    )

    queue = ValidationJobQueue(settings, max_concurrency=settings.validation_max_concurrency)
    job_ids: list[uuid.UUID] = []
    job_dirs: dict[uuid.UUID, Path] = {}

    t0 = time.perf_counter()
    for _ in range(args.jobs):
        jid = uuid.uuid4()
        job_dir = _create_job_dir(settings, jid)
        job_ids.append(jid)
        job_dirs[jid] = job_dir
        queue.enqueue(jid, job_dir)
    submit_elapsed = time.perf_counter() - t0

    print(f"Submitted {args.jobs} jobs in {submit_elapsed:.2f}s (serial FIFO queue)")
    print(f"Source: {SOURCE} ({SOURCE.stat().st_size / 1024**3:.1f} GiB)")
    print(f"Target: {TARGET} ({TARGET.stat().st_size / 1024**3:.1f} GiB)")

    records = asyncio.run(_wait_for_jobs(queue, job_ids))
    wall = time.perf_counter() - t0

    enriched = []
    for rec in records:
        jid = uuid.UUID(rec["job_id"])
        job_dir = job_dirs[jid]
        val_s = _validation_seconds(job_dir)
        queue_wait = None
        run_s = None
        if rec["started_at"] and rec["enqueued_at"]:
            queue_wait = rec["started_at"] - rec["enqueued_at"]
        if rec["started_at"] and rec["finished_at"]:
            run_s = rec["finished_at"] - rec["started_at"]
        enriched.append(
            {
                **rec,
                "queue_wait_seconds": round(queue_wait, 2) if queue_wait is not None else None,
                "worker_wall_seconds": round(run_s, 2) if run_s is not None else None,
                "validation_seconds": round(val_s, 2) if val_s is not None else None,
            }
        )

    val_times = [r["validation_seconds"] for r in enriched if r["validation_seconds"]]
    summary = {
        "jobs_submitted": args.jobs,
        "submit_burst_seconds": round(submit_elapsed, 2),
        "total_wall_seconds": round(wall, 2),
        "total_wall_minutes": round(wall / 60, 2),
        "per_job_validation_seconds": val_times,
        "avg_validation_seconds": round(sum(val_times) / len(val_times), 2) if val_times else None,
        "all_states": [r["state"] for r in enriched],
        "serial_fifo": True,
        "jobs": enriched,
    }
    out = REPO / "pegasus-backend" / "load_test_100m_results.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
