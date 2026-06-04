# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T12:06:25+05:30
# --- END GENERATED FILE METADATA ---

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
    auto_in_memory_max_bytes: int = 256 * 1024 * 1024
    memory_budget_bytes: int = 1_073_741_824
    disk_headroom_multiplier: float = 2.5
    fingerprint_algorithm: str = "xxhash64"
    polars_spill_max_bytes: int = 256 * 1024 * 1024
    force_disk_spill: bool = False
    enable_merkle_fast_path: bool = True
    enable_content_digest_precheck: bool = True
    spill_merkle_max_bytes: int = 32 * 1024 * 1024

    def resolved_partition_count(self) -> int:
        if self.partition_preset and self.partition_preset in _PARTITION_PRESETS:
            preset = _PARTITION_PRESETS[self.partition_preset]
            return min(self.partition_count, preset) if self.partition_count else preset
        return max(1024, self.partition_count)
