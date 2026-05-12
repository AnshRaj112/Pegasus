"""Resumable execution metadata (design hook; callers may persist JSON to disk)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ReconciliationCheckpoint:
    """Opaque progress snapshot for crash-safe reruns.

    Future workers can extend fields (byte offsets, parquet shard indices, etc.)
    without changing coordinator call sites.
    """

    run_id: str
    phase: str
    source_paths: list[str]
    target_paths: list[str]
    extra: dict[str, Any]

    def to_json(self) -> str:
        """Serialize to JSON for ``Path.write_text``."""
        return json.dumps(asdict(self), indent=2, default=str)

    @classmethod
    def from_json(cls, raw: str) -> ReconciliationCheckpoint:
        """Deserialize JSON written by :meth:`to_json`."""
        data = json.loads(raw)
        return cls(
            run_id=str(data["run_id"]),
            phase=str(data["phase"]),
            source_paths=list(data["source_paths"]),
            target_paths=list(data["target_paths"]),
            extra=dict(data.get("extra") or {}),
        )

    def write(self, path: Path) -> None:
        """Atomically best-effort write (replace)."""
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> ReconciliationCheckpoint:
        """Load a checkpoint written with :meth:`write`."""
        return cls.from_json(path.read_text(encoding="utf-8"))
