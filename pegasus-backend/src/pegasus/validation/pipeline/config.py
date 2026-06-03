"""Pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass

_PARTITION_PRESETS: dict[str, int] = {
    "small": 1024,
    "medium": 2048,
    "large": 4096,
    "xlarge": 8192,
}


@dataclass(slots=True)
class TabularPipelineConfig:
    chunk_rows: int = 10_000
    partition_count: int = 2048
    partition_preset: str | None = "medium"
    enable_column_drilldown: bool = True
    enable_in_memory_reconcile: bool = False
    memory_budget_bytes: int = 1_073_741_824
    disk_headroom_multiplier: float = 2.5

    def resolved_partition_count(self) -> int:
        if self.partition_preset and self.partition_preset in _PARTITION_PRESETS:
            preset = _PARTITION_PRESETS[self.partition_preset]
            return min(self.partition_count, preset) if self.partition_count else preset
        return max(1024, self.partition_count)
