# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T07:01:32Z
# --- END GENERATED FILE METADATA ---

"""Pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass

from pegasus.validation.comparators.policy import ComparePolicy

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
    lazy_column_drilldown: bool = True
    use_columnar_spill: bool = True
    use_arrow_ipc_spill: bool = True
    fingerprint_only_spill: bool = True
    force_native_multichar_spill: bool = True
    gcs_streaming_only: bool = False  # noqa: kept for service wiring; prefetch gated in ValidationService
    enable_in_memory_reconcile: bool = False
    auto_in_memory_max_bytes: int = 256 * 1024 * 1024
    memory_budget_bytes: int = 1_073_741_824
    disk_headroom_multiplier: float = 1.5
    fingerprint_algorithm: str = "xxhash64"
    polars_spill_max_bytes: int = 256 * 1024 * 1024
    force_disk_spill: bool = False
    enable_merkle_fast_path: bool = True
    enable_content_digest_precheck: bool = False
    spill_merkle_max_bytes: int = 32 * 1024 * 1024
    partition_reconcile_workers: int = 1
    streaming_spill_min_bytes: int = 64 * 1024 * 1024
    partition_wave_size: int = 0
    wave_min_bytes: int = 512 * 1024 * 1024
    partition_reconcile_use_processes: bool = True
    distributed_enabled: bool = False
    distributed_redis_url: str | None = None
    distributed_job_id: str | None = None
    distributed_min_bytes: int = 10 * 1024 * 1024 * 1024
    compare_policy: ComparePolicy | None = None

    def resolved_partition_count(self) -> int:
        if self.partition_preset and self.partition_preset in _PARTITION_PRESETS:
            preset = _PARTITION_PRESETS[self.partition_preset]
            return min(self.partition_count, preset) if self.partition_count else preset
        return max(1024, self.partition_count)
