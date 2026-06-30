# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T06:21:03Z
# --- END GENERATED FILE METADATA ---

"""Redis-backed coordinator for partition reconcile tasks."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Iterable

from pegasus.validation.workers.partition_task import PartitionTask

logger = logging.getLogger(__name__)

TASK_QUEUE_KEY = "pegasus:partition_tasks"
RESULT_QUEUE_PREFIX = "pegasus:partition_results:"


class DistributedReconciliationCoordinator:
    """Enqueue partition reconcile tasks and collect results."""

    def __init__(self, *, redis_url: str, work_dir: Path) -> None:
        self._redis_url = redis_url
        self._work_dir = work_dir
        self._client = None

    def _redis(self):
        if self._client is None:
            import redis

            self._client = redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def clear_results(self, job_id: str) -> None:
        self._redis().delete(f"{RESULT_QUEUE_PREFIX}{job_id}")

    def enqueue_partitions(self, job_id: str, partition_ids: Iterable[int]) -> int:
        """Push partition tasks to Redis; return count enqueued."""
        client = self._redis()
        count = 0
        for pid in partition_ids:
            src = self._work_dir / "source" / f"part_{pid:05d}.bin"
            tgt = self._work_dir / "target" / f"part_{pid:05d}.bin"
            if not src.is_file() or not tgt.is_file():
                continue
            task = PartitionTask(
                job_id=job_id,
                partition_id=pid,
                source_spill_path=str(src),
                target_spill_path=str(tgt),
            )
            client.lpush(TASK_QUEUE_KEY, json.dumps(task.to_dict()))
            count += 1
        logger.info("Enqueued %d partition tasks for job %s", count, job_id)
        return count

    def reconcile_partitions(
        self,
        job_id: str,
        partition_ids: list[int],
        *,
        timeout_seconds: float = 3600,
    ) -> tuple[int, int, int, int, int] | None:
        """Enqueue partitions, wait for worker results, return aggregate counts or None."""
        self.clear_results(job_id)
        expected = self.enqueue_partitions(job_id, partition_ids)
        if expected <= 0:
            return None

        client = self._redis()
        result_key = f"{RESULT_QUEUE_PREFIX}{job_id}"
        missing = extra = changed = matching = 0
        mismatched_partitions = 0
        received = 0
        deadline = time.monotonic() + timeout_seconds

        while received < expected and time.monotonic() < deadline:
            wait_s = min(5, max(1, int(deadline - time.monotonic())))
            item = client.brpop(result_key, timeout=wait_s)
            if item is None:
                continue
            received += 1
            try:
                data = json.loads(item[1])
                stats = data.get("stats") or {}
                part_missing = int(stats.get("missing", 0))
                part_extra = int(stats.get("extra", 0))
                part_changed = int(stats.get("changed", 0))
                part_matching = int(stats.get("matching", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            missing += part_missing
            extra += part_extra
            changed += part_changed
            matching += part_matching
            if part_missing or part_extra or part_changed:
                mismatched_partitions += 1

        if received < expected:
            logger.warning(
                "Distributed reconcile incomplete job=%s received=%d expected=%d",
                job_id,
                received,
                expected,
            )
            return None
        return missing, extra, changed, matching, mismatched_partitions

    def wait_for_results(self, job_id: str, expected: int, *, timeout_seconds: float = 3600) -> int:
        """Block until *expected* result messages arrive or timeout."""
        client = self._redis()
        result_key = f"{RESULT_QUEUE_PREFIX}{job_id}"
        received = 0
        deadline = time.monotonic() + timeout_seconds
        while received < expected and time.monotonic() < deadline:
            wait_s = min(5, max(1, int(deadline - time.monotonic())))
            item = client.brpop(result_key, timeout=wait_s)
            if item is None:
                continue
            received += 1
        return received

    @staticmethod
    def available(redis_url: str | None) -> bool:
        if not redis_url:
            return False
        try:
            import redis

            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            return True
        except Exception:
            return False

    @staticmethod
    def should_use(
        *,
        enabled: bool,
        redis_url: str | None,
        combined_bytes: int,
        min_bytes: int,
    ) -> bool:
        return (
            enabled
            and combined_bytes >= min_bytes
            and DistributedReconciliationCoordinator.available(redis_url)
        )
