"""Configuration for external-memory reconciliation strategies."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ReconciliationStrategy(StrEnum):
    """Comparison strategy selection for the coordinator."""

    AUTO = "auto"
    """Pick a strategy from file size hints and :attr:`ReconciliationRuntimeConfig.assume_sorted`."""

    ORDERED_STREAM = "ordered_stream"
    """Two-pointer merge on streams; requires globally sorted CSV rows by UID."""

    SLIDING_WINDOW = "sliding_window"
    """Like :attr:`ORDERED_STREAM` with bounded look-ahead on each side for minor skew."""

    HASH_PARTITION = "hash_partition"
    """Spill rows into ``hash(uid) % N`` buckets, then compare bucket-wise."""

    EXTERNAL_SORT = "external_sort"
    """Sort-and-spill each side, then run :attr:`ORDERED_STREAM` on sorted outputs."""

    GNU_SORT = "gnu_sort"
    """Use system `sort` and `comm` for maximum performance (Unix/macOS only)."""


class ReconciliationRuntimeConfig(BaseModel):
    """User-tunable knobs for chunking, partitioning, and temp storage."""

    model_config = {"frozen": True}

    strategy: ReconciliationStrategy = Field(
        default=ReconciliationStrategy.AUTO,
        description="Active reconciliation strategy (or AUTO).",
    )
    chunk_rows: int = Field(default=1_000_000, ge=1024, le=5_000_000)
    partition_buckets: int = Field(default=16, ge=1, le=4096)
    sliding_window: int = Field(
        default=0,
        ge=0,
        le=1_000_000,
        description="Row look-ahead on each side for SLIDING_WINDOW; 0 disables look-ahead.",
    )
    assume_sorted: bool = Field(
        default=False,
        description="If True, ORDERED_STREAM / SLIDING_WINDOW may scan CSV batches sequentially.",
    )
    temp_dir: Path | None = Field(
        default=None,
        description="Optional base directory for spill files; default uses system temp.",
    )
    retry_max_attempts: int = Field(default=3, ge=1, le=10)
    external_memory_threshold_bytes: int = Field(
        default=25 * 1024 * 1024,
        ge=0,
        description="AUTO uses external strategies when source+target file size exceeds this sum.",
    )
    stringify_null_in_report: bool = Field(default=True)

    sub_partition_buckets: int = Field(
        default=1,
        ge=1,
        le=256,
        description=(
            "Secondary hash buckets per primary partition (1 = disabled). "
            "Uses extra SHA-256 digest bits so skewed primary buckets are split on disk."
        ),
    )
    parallel_spill_sides: bool = Field(
        default=True,
        description="When True, spill source and target CSVs concurrently (two readers, separate sides).",
    )
    parallel_partition_comparison: bool = Field(
        default=True,
        description="When True, compare hash partitions in parallel using multiple processes.",
    )
    disk_headroom_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=10.0,
        description="Minimum free disk bytes >= multiplier × (source_size + target_size) before spill.",
    )
    mismatch_ndjson_mirror: bool = Field(
        default=False,
        description="When True, append every flushed mismatch chunk to mismatch_mirror.ndjson under the workspace.",
    )
    force_external: bool = Field(
        default=False,
        description="When True, AUTO strategy still selects external paths for small combined file sizes.",
    )
    stream_mismatches: bool = Field(
        default=True,
        description="When True, mismatch rows are appended to NDJSON on disk instead of a giant in-memory frame.",
    )
    artifact_export_path: Path | None = Field(
        default=None,
        description="When set, streaming mismatch NDJSON is copied here before the spill workspace is removed.",
    )
    max_parallel_workers: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of parallel workers for partition comparison. If None, uses CPU count.",
    )
    has_header: bool = Field(
        default=True,
        description="When false, CSV files have no header row (columns are column_1, column_2, …).",
    )
    memory_budget_bytes: int = Field(
        default=10 * 1024 * 1024 * 1024,
        ge=256 * 1024 * 1024,
        description="Hard per-job RAM budget used for runtime tuning and guardrails.",
    )
    target_duration_seconds: int = Field(
        default=15 * 60,
        ge=60,
        le=24 * 60 * 60,
        description="Target completion time used to bias chunk sizing and worker concurrency.",
    )
    enable_merkle_fast_path: bool = Field(
        default=True,
        description="When true, run an ordered streaming Merkle precheck and short-circuit if roots match exactly.",
    )

    def with_overrides(self, **kwargs: Any) -> ReconciliationRuntimeConfig:
        """Return a copy with merged fields (convenience for tests)."""
        return self.model_copy(update=kwargs)
