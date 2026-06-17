# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:52:37Z
# --- END GENERATED FILE METADATA ---

"""Kubernetes-compatible partition worker with checkpointing."""

import json
import time
from pathlib import Path
from typing import Optional
from uuid import UUID

from category1.core.external_memory import MemoryMonitor
from category1.core.mismatch_detector import MismatchDetector
from category1.core.partitioner import PartitionWriter
from category1.models.schemas import MismatchRecord, PartitionStats, ReconciliationJobConfig


class Checkpoint:
    """Persists worker state for failure recovery."""

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, job_id: UUID, partition_id: int, state: dict) -> None:
        path = self.checkpoint_dir / f"{job_id}_part_{partition_id:05d}.json"
        path.write_text(json.dumps(state, default=str))

    def load(self, job_id: UUID, partition_id: int) -> Optional[dict]:
        path = self.checkpoint_dir / f"{job_id}_part_{partition_id:05d}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    def list_completed(self, job_id: UUID) -> list[int]:
        completed = []
        for path in self.checkpoint_dir.glob(f"{job_id}_part_*.json"):
            state = json.loads(path.read_text())
            if state.get("status") == "completed":
                completed.append(state["partition_id"])
        return completed

    def mark_completed(self, job_id: UUID, partition_id: int, stats: PartitionStats) -> None:
        self.save(job_id, partition_id, {
            "status": "completed",
            "partition_id": partition_id,
            "stats": stats.model_dump(),
            "timestamp": time.time(),
        })


class PartitionWorker:
    """
    Stateless worker that processes a single partition.
    Designed for horizontal scaling in Kubernetes.
    """

    def __init__(
        self,
        job_config: ReconciliationJobConfig,
        work_dir: Path,
        memory_limit_mb: int = 1024,
    ):
        self.job_config = job_config
        self.work_dir = work_dir
        self.memory_monitor = MemoryMonitor(memory_limit_mb)
        self.checkpoint = Checkpoint(work_dir / "checkpoints")

    def process_partition(self, partition_id: int) -> tuple[PartitionStats, list[MismatchRecord]]:
        existing = self.checkpoint.load(self.job_config.job_id, partition_id)
        if existing and existing.get("status") == "completed":
            stats = PartitionStats(**existing["stats"])
            return stats, []

        source_path = self.work_dir / "source" / "partitions" / f"part_{partition_id:05d}.bin"
        target_path = self.work_dir / "target" / "partitions" / f"part_{partition_id:05d}.bin"
        spill_dir = self.work_dir / "spill" / f"part_{partition_id:05d}"

        compare_columns = self.job_config.compare_columns or self.job_config.key_columns
        detector = MismatchDetector(
            compare_columns,
            self.job_config.column_mapping,
            enable_drilldown=self.job_config.enable_column_drilldown,
        )

        stats, mismatches = detector.reconcile_partition(
            source_path, target_path, partition_id, spill_dir, self.memory_monitor,
        )

        self.checkpoint.mark_completed(self.job_config.job_id, partition_id, stats)
        return stats, mismatches


class WorkQueue:
    """Simple Redis-backed work queue for partition tasks."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis = None

    def _get_redis(self):
        if self._redis is None:
            import redis
            self._redis = redis.from_url(self.redis_url)
        return self._redis

    def enqueue_partitions(self, job_id: UUID, partition_ids: list[int]) -> None:
        r = self._get_redis()
        for pid in partition_ids:
            r.rpush(f"category1:queue:{job_id}", json.dumps({"partition_id": pid}))

    def dequeue_partition(self, job_id: UUID, timeout: int = 30) -> Optional[int]:
        r = self._get_redis()
        result = r.blpop(f"category1:queue:{job_id}", timeout=timeout)
        if result:
            data = json.loads(result[1])
            return data["partition_id"]
        return None

    def get_queue_length(self, job_id: UUID) -> int:
        return self._get_redis().llen(f"category1:queue:{job_id}")
