# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:27:35Z
# --- END GENERATED FILE METADATA ---

"""CLI entrypoint for distributed partition reconcile workers."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

from pegasus.validation.pipeline.partition_reconcile import reconcile_partition_core
from pegasus.validation.workers.checkpoint import PartitionCheckpoint
from pegasus.validation.workers.coordinator import RESULT_QUEUE_PREFIX, TASK_QUEUE_KEY
from pegasus.validation.workers.partition_task import PartitionTask

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, os.environ.get("PEGASUS_LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def run_worker_loop(*, redis_url: str, work_dir: Path, checkpoint_dir: Path | None = None) -> None:
    import redis

    client = redis.from_url(redis_url, decode_responses=True)
    checkpoint = PartitionCheckpoint(checkpoint_dir or work_dir / "checkpoints")
    logger.info("Partition worker started redis=%s work_dir=%s", redis_url, work_dir)
    while True:
        item = client.brpop(TASK_QUEUE_KEY, timeout=5)
        if item is None:
            continue
        _queue, payload = item
        try:
            task = PartitionTask.from_dict(json.loads(payload))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.warning("Skipping malformed partition task")
            continue
        if checkpoint.is_completed(task.job_id, task.partition_id):
            continue
        try:
            core = reconcile_partition_core(
                Path(task.source_spill_path),
                Path(task.target_spill_path),
                sample_limit=task.sample_limit,
            )
            stats = {
                "missing": core.missing,
                "extra": core.extra,
                "changed": core.changed,
                "matching": core.matching,
            }
            checkpoint.mark_completed(task.job_id, task.partition_id, stats)
            result_key = f"{RESULT_QUEUE_PREFIX}{task.job_id}"
            client.lpush(
                result_key,
                json.dumps(
                    {
                        "partition_id": task.partition_id,
                        "stats": stats,
                        "missing_keys": core.missing_keys[: task.sample_limit],
                        "extra_keys": core.extra_keys[: task.sample_limit],
                        "changed_keys": core.changed_keys[: task.sample_limit],
                        "completed_at": time.time(),
                    }
                ),
            )
        except Exception:
            logger.exception(
                "Partition reconcile failed job=%s partition=%d",
                task.job_id,
                task.partition_id,
            )


def main() -> int:
    _configure_logging()
    redis_url = os.environ.get("PEGASUS_VALIDATION_REDIS_URL") or os.environ.get("REDIS_URL")
    if not redis_url:
        logger.error("PEGASUS_VALIDATION_REDIS_URL or REDIS_URL is required")
        return 1
    work_dir = Path(os.environ.get("PEGASUS_VALIDATION_WORK_DIR", "/data/pegasus/work"))
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_worker_loop(redis_url=redis_url, work_dir=work_dir)
    except KeyboardInterrupt:
        logger.info("Partition worker shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
