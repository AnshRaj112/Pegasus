# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T06:20:06Z
# --- END GENERATED FILE METADATA ---

"""Checkpoint persistence for distributed partition workers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class PartitionCheckpoint:
    """Persists completed partition ids for crash recovery."""

    def __init__(self, checkpoint_dir: Path) -> None:
        self._dir = checkpoint_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def mark_completed(self, job_id: str, partition_id: int, stats: dict[str, Any]) -> None:
        path = self._dir / f"{job_id}_part_{partition_id:05d}.json"
        path.write_text(
            json.dumps(
                {
                    "status": "completed",
                    "partition_id": partition_id,
                    "stats": stats,
                    "timestamp": time.time(),
                },
                default=str,
            ),
            encoding="utf-8",
        )

    def is_completed(self, job_id: str, partition_id: int) -> bool:
        path = self._dir / f"{job_id}_part_{partition_id:05d}.json"
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("status") == "completed"
        except (OSError, ValueError, TypeError):
            return False

    def list_completed(self, job_id: str) -> list[int]:
        completed: list[int] = []
        for path in self._dir.glob(f"{job_id}_part_*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("status") == "completed":
                    completed.append(int(data["partition_id"]))
            except (OSError, ValueError, TypeError, KeyError):
                continue
        return sorted(completed)
