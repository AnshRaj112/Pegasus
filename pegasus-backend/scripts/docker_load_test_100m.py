#!/usr/bin/env python3
"""Submit multiple 100M×12-col validations through the Docker API and measure queue behavior.

Runs from the **host** (not inside a container). Pegasus backend + validation-worker must be up:

    docker compose up --build

Example (paths must exist inside backend/worker containers via volume mount):

    python pegasus-backend/scripts/docker_load_test_100m.py \\
        --jobs 3 \\
        --source-path /home/onix/Pegasus/test-data/generated-100m-12cols/source.csv \\
        --target-path /home/onix/Pegasus/test-data/generated-100m-12cols/target.csv

    # Or burst-submit 2 jobs at once to test FCFS + large-job queueing:
    python pegasus-backend/scripts/docker_load_test_100m.py --jobs 2 --burst

Results are printed as JSON and written to load_test_docker_100m_results.json in the repo root.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPO / "test-data/generated-100m-12cols/source.csv"
DEFAULT_TARGET = REPO / "test-data/generated-100m-12cols/target.csv"

COMPARE_COLUMNS = [
    "sku",
    "amount",
    "region",
    "attr4",
    "attr5",
    "attr6",
    "attr7",
    "attr8",
    "attr9",
    "attr10",
    "attr11",
]


def _http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    *,
    timeout: float = 120.0,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw.strip() else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {"detail": raw}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def _validate_payload(source_path: str, target_path: str) -> dict[str, Any]:
    return {
        "source_path": source_path,
        "target_path": target_path,
        "uid_column": "id",
        "delimiter": "||",
        "file_format": "csv",
        "has_header": True,
        "header_leading_rows": 0,
        "validate_header_formats": False,
        "validate_footers": False,
        "footer_trailing_rows": 1,
        "test_mode": "full",
        "column_mappings": [{"source_column": c, "target_column": c} for c in COMPARE_COLUMNS],
    }


def _submit_job(api_base: str, source_path: str, target_path: str) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/validate/local"
    status, payload = _http_json("POST", url, _validate_payload(source_path, target_path), timeout=300.0)
    if status != 202:
        raise RuntimeError(f"Submit failed HTTP {status}: {payload}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected submit response: {payload!r}")
    return payload


def _poll_job(api_base: str, job_id: str) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/validate/jobs/{job_id}?summary_only=true"
    status, payload = _http_json("GET", url, timeout=60.0)
    if status != 200:
        raise RuntimeError(f"Poll failed HTTP {status} job={job_id}: {payload}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected poll response: {payload!r}")
    return payload


def _queue_stats(api_base: str) -> dict[str, Any] | None:
    url = f"{api_base.rstrip('/')}/validate/queue"
    status, payload = _http_json("GET", url, timeout=30.0)
    if status != 200 or not isinstance(payload, dict):
        return None
    return payload


def _wait_for_jobs(
    api_base: str,
    job_ids: list[str],
    *,
    poll_interval: float,
) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {
        jid: {
            "job_id": jid,
            "submitted_at": None,
            "accepted_status": None,
            "queue_position": None,
            "started_epoch": None,
            "finished_epoch": None,
            "final_status": None,
            "queue_reason": None,
            "error": None,
            "validation_seconds": None,
            "is_match": None,
        }
        for jid in job_ids
    }
    t0 = time.time()

    while True:
        all_terminal = True
        for jid in job_ids:
            rec = records[jid]
            try:
                job = _poll_job(api_base, jid)
            except Exception as exc:
                rec["error"] = str(exc)
                all_terminal = False
                continue

            st = str(job.get("status") or "").lower()
            rec["final_status"] = st
            progress = job.get("progress") if isinstance(job.get("progress"), dict) else {}
            if isinstance(progress, dict):
                reason = progress.get("queue_reason")
                if isinstance(reason, str) and reason.strip():
                    rec["queue_reason"] = reason.strip()

            if st in ("queued", "running"):
                all_terminal = False
                if st == "running" and rec["started_epoch"] is None:
                    rec["started_epoch"] = time.time()
            elif st in ("completed", "failed"):
                if rec["finished_epoch"] is None:
                    rec["finished_epoch"] = time.time()
                if st == "failed":
                    rec["error"] = str(job.get("error") or job.get("message") or "failed")
                result = job.get("result")
                if isinstance(result, dict):
                    rec["is_match"] = result.get("is_match")
                    durations = result.get("durations") if isinstance(result.get("durations"), dict) else {}
                    val_s = durations.get("validation_seconds") if isinstance(durations, dict) else None
                    if val_s is not None:
                        rec["validation_seconds"] = float(val_s)
            else:
                all_terminal = False

        if all_terminal:
            break
        if time.time() - t0 > 4 * 3600:
            raise TimeoutError(f"Timed out after 4h waiting for jobs: {job_ids}")
        time.sleep(poll_interval)

    for rec in records.values():
        if rec["submitted_at"] and rec["started_epoch"]:
            rec["queue_wait_seconds"] = round(rec["started_epoch"] - rec["submitted_at"], 2)
        if rec["started_epoch"] and rec["finished_epoch"]:
            rec["wall_run_seconds"] = round(rec["finished_epoch"] - rec["started_epoch"], 2)

    return [records[jid] for jid in job_ids]


def main() -> int:
    parser = argparse.ArgumentParser(description="Docker API load test: 100M×12-col validations")
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8000/api/v1",
        help="Pegasus API base URL (default: http://127.0.0.1:8000/api/v1)",
    )
    parser.add_argument(
        "--source-path",
        default=str(DEFAULT_SOURCE),
        help="Source CSV path as seen inside backend/worker containers",
    )
    parser.add_argument(
        "--target-path",
        default=str(DEFAULT_TARGET),
        help="Target CSV path as seen inside backend/worker containers",
    )
    parser.add_argument("--jobs", type=int, default=2, help="Number of validation jobs to submit")
    parser.add_argument(
        "--burst",
        action="store_true",
        help="Submit all jobs immediately (default: 2s pause between submits)",
    )
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between status polls")
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="Verify fixture files exist on this host before submitting",
    )
    args = parser.parse_args()

    if args.jobs < 1:
        print("error: --jobs must be >= 1", file=sys.stderr)
        return 2

    if args.check_files:
        src = Path(args.source_path)
        tgt = Path(args.target_path)
        if not src.is_file() or not tgt.is_file():
            print(
                json.dumps(
                    {
                        "error": "fixture missing on this host",
                        "source": str(src),
                        "target": str(tgt),
                        "hint": "Omit --check-files if paths only exist on the Docker host mount",
                    },
                    indent=2,
                )
            )
            return 1

    print(f"API: {args.api_base}")
    print(f"Source: {args.source_path}")
    print(f"Target: {args.target_path}")
    print(f"Submitting {args.jobs} job(s)…")

    submitted: list[dict[str, Any]] = []
    job_ids: list[str] = []
    t_submit_start = time.perf_counter()

    for i in range(args.jobs):
        t_one = time.time()
        try:
            accepted = _submit_job(args.api_base, args.source_path, args.target_path)
        except Exception as exc:
            print(json.dumps({"error": f"submit {i + 1} failed", "detail": str(exc)}, indent=2))
            return 1
        jid = str(accepted.get("job_id") or "")
        if not jid:
            print(json.dumps({"error": "no job_id in response", "response": accepted}, indent=2))
            return 1
        job_ids.append(jid)
        submitted.append(
            {
                "index": i,
                "job_id": jid,
                "submitted_at": t_one,
                "accepted_status": accepted.get("status"),
                "queue_position": accepted.get("queue_position"),
                "queue_pending": accepted.get("queue_pending"),
                "queue_running": accepted.get("queue_running"),
            }
        )
        print(
            f"  [{i + 1}/{args.jobs}] job_id={jid} status={accepted.get('status')} "
            f"pending={accepted.get('queue_pending')} running={accepted.get('queue_running')}"
        )
        if not args.burst and i + 1 < args.jobs:
            time.sleep(2.0)

    submit_elapsed = time.perf_counter() - t_submit_start
    queue_snap = _queue_stats(args.api_base)

    print(f"\nWaiting for {len(job_ids)} job(s) (poll every {args.poll_interval}s)…")
    results = _wait_for_jobs(args.api_base, job_ids, poll_interval=args.poll_interval)

    for rec, sub in zip(results, submitted):
        rec["submitted_at"] = sub["submitted_at"]
        rec["accepted_status"] = sub["accepted_status"]
        rec["initial_queue_position"] = sub["queue_position"]

    wall = time.perf_counter() - t_submit_start
    val_times = [r["validation_seconds"] for r in results if r.get("validation_seconds") is not None]

    summary = {
        "api_base": args.api_base,
        "source_path": args.source_path,
        "target_path": args.target_path,
        "jobs_submitted": args.jobs,
        "submit_mode": "burst" if args.burst else "paced_2s",
        "submit_elapsed_seconds": round(submit_elapsed, 2),
        "total_wall_seconds": round(wall, 2),
        "total_wall_minutes": round(wall / 60, 2),
        "queue_snapshot_after_submit": queue_snap,
        "validation_seconds": val_times,
        "avg_validation_seconds": round(sum(val_times) / len(val_times), 2) if val_times else None,
        "all_final_statuses": [r.get("final_status") for r in results],
        "all_errors": [r.get("error") for r in results if r.get("error")],
        "backend_alive": True,
        "jobs": results,
    }

    out_path = REPO / "load_test_docker_100m_results.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")

    if any(r.get("final_status") == "failed" for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
