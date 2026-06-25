# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:10:34Z
# --- END GENERATED FILE METADATA ---

"""Serializable partition reconcile task."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PartitionTask:
    job_id: str
    partition_id: int
    source_spill_path: str
    target_spill_path: str
    sample_limit: int = 1000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PartitionTask:
        return cls(
            job_id=str(data["job_id"]),
            partition_id=int(data["partition_id"]),
            source_spill_path=str(data["source_spill_path"]),
            target_spill_path=str(data["target_spill_path"]),
            sample_limit=int(data.get("sample_limit") or 1000),
        )
