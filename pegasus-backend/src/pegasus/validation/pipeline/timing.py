# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T12:06:25+05:30
# --- END GENERATED FILE METADATA ---

"""Pipeline stage timing for performance profiling."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PipelineTimings:
    source_read_seconds: float = 0.0
    target_read_seconds: float = 0.0
    source_partition_seconds: float = 0.0
    target_partition_seconds: float = 0.0
    canonicalization_seconds: float = 0.0
    identity_generation_seconds: float = 0.0
    fingerprint_generation_seconds: float = 0.0
    partition_calculation_seconds: float = 0.0
    serialization_seconds: float = 0.0
    disk_write_seconds: float = 0.0
    disk_read_seconds: float = 0.0
    partition_reconciliation_seconds: float = 0.0
    column_comparison_seconds: float = 0.0
    report_generation_seconds: float = 0.0
    network_transfer_seconds: float = 0.0
    total_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_read_seconds": round(self.source_read_seconds, 4),
            "target_read_seconds": round(self.target_read_seconds, 4),
            "canonicalization_seconds": round(self.canonicalization_seconds, 4),
            "identity_generation_seconds": round(self.identity_generation_seconds, 4),
            "fingerprint_generation_seconds": round(self.fingerprint_generation_seconds, 4),
            "partition_calculation_seconds": round(self.partition_calculation_seconds, 4),
            "serialization_seconds": round(self.serialization_seconds, 4),
            "disk_write_seconds": round(self.disk_write_seconds, 4),
            "disk_read_seconds": round(self.disk_read_seconds, 4),
            "partition_reconciliation_seconds": round(self.partition_reconciliation_seconds, 4),
            "column_comparison_seconds": round(self.column_comparison_seconds, 4),
            "report_generation_seconds": round(self.report_generation_seconds, 4),
            "network_transfer_seconds": round(self.network_transfer_seconds, 4),
            "total_seconds": round(self.total_seconds, 4),
        }


class StageTimer:
    """Accumulate elapsed time into a PipelineTimings field."""

    __slots__ = ("_timings", "_field", "_start")

    def __init__(self, timings: PipelineTimings, field_name: str) -> None:
        self._timings = timings
        self._field = field_name
        self._start = 0.0

    def __enter__(self) -> StageTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        elapsed = time.perf_counter() - self._start
        current = getattr(self._timings, self._field)
        setattr(self._timings, self._field, current + elapsed)
