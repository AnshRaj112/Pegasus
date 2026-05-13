"""Configuration for external-memory reconciliation strategies."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ReconciliationBackend(StrEnum):
    """Which engine performs disk-backed joins and CSV ingestion."""

    DUCKDB = "duckdb"
    """DuckDB external-memory joins (recommended for large unsorted CSV pairs)."""

    POLARS = "polars"
    """Polars spill / hash-partition / external sort pipeline."""


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
    backend: ReconciliationBackend = Field(
        default=ReconciliationBackend.POLARS,
        description="POLARS uses the spill/hash-partition pipeline (default); DUCKDB uses DuckDB for the same joins.",
    )
    force_external: bool = Field(
        default=False,
        description="When True, AUTO strategy still selects external paths for small combined file sizes.",
    )
    stream_mismatches: bool = Field(
        default=True,
        description="When True, mismatch rows are appended to NDJSON on disk instead of a giant in-memory frame.",
    )
    duckdb_memory_limit_ratio: float = Field(
        default=1.00,
        ge=0.10,
        le=1.00,
        description="Fraction of (physical RAM minus duckdb_memory_os_reserve_bytes) for DuckDB memory_limit.",
    )
    duckdb_memory_os_reserve_bytes: int = Field(
        default=512 * 1024 * 1024,
        ge=0,
        le=32 * 1024 * 1024 * 1024,
        description="RAM reserved for OS / Python when computing DuckDB memory_limit.",
    )
    duckdb_network_threads: int = Field(
        default=2,
        ge=1,
        le=64,
        description="DuckDB threads when source/target live on network filesystems (reduce I/O saturation).",
    )
    duckdb_local_threads: int = Field(
        default=0,
        ge=0,
        le=256,
        description="DuckDB threads on local storage (0 => auto os.cpu_count()).",
    )
    duckdb_enable_object_cache: bool = Field(
        default=True,
        description="Enable DuckDB object cache for local files.",
    )
    duckdb_explain_analyze: bool = Field(
        default=False,
        description=(
            "When True, run EXPLAIN ANALYZE for key DuckDB stages and log operator-level profiles "
            "(diagnostic mode; adds overhead)."
        ),
    )
    duckdb_ingest_csv_to_parquet: bool = Field(
        default=True,
        description=(
            "When True, DuckDB streams each CSV into a ZSTD-compressed Parquet working file "
            "with a precomputed pegasus_part column before reconciliation."
        ),
    )
    duckdb_parquet_row_group_size: int = Field(
        default=1_048_576,
        ge=1024,
        le=10_000_000,
        description="Target Parquet row group size for DuckDB COPY ... FORMAT PARQUET during CSV ingest.",
    )
    duckdb_reconciliation_partitions: int = Field(
        default=0,
        ge=0,
        le=4096,
        description=(
            "Partition count for DuckDB hash(uid)%%N reconciliation (0 = use partition_buckets). "
            "Smaller joins per round reduce peak memory vs one global join."
        ),
    )
    duckdb_parallel_csv_ingest: bool = Field(
        default=True,
        description=(
            "When True, DuckDB CSV→Parquet ingest runs source and target in parallel threads "
            "(each with its own DuckDB connection; memory_limit is halved per connection)."
        ),
    )
    artifact_export_path: Path | None = Field(
        default=None,
        description="When set, streaming mismatch NDJSON is copied here before the spill workspace is removed.",
    )

    def with_overrides(self, **kwargs: Any) -> ReconciliationRuntimeConfig:
        """Return a copy with merged fields (convenience for tests)."""
        return self.model_copy(update=kwargs)
