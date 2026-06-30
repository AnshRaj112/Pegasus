# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:41:59Z
# --- END GENERATED FILE METADATA ---

"""Platform configuration with bounded-memory defaults."""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class StorageBackend(str, Enum):
    LOCAL = "local"
    OBJECT = "object"
    SQLITE = "sqlite"


class ReconciliationConfig(BaseSettings):
    """Runtime configuration for reconciliation jobs."""

    chunk_size: int = Field(default=10000, ge=1000, le=50000)
    num_partitions: int = Field(default=4096, ge=1024, le=8192)
    memory_limit_mb: int = Field(default=1024, ge=256)
    spill_threshold_pct: float = Field(default=0.75, ge=0.5, le=0.95)
    work_dir: Path = Field(default=Path("/tmp/category1"))
    storage_backend: StorageBackend = StorageBackend.LOCAL
    object_storage_bucket: Optional[str] = None
    object_storage_endpoint: Optional[str] = None
    max_concurrent_partitions: int = Field(default=4, ge=1, le=64)
    enable_row_count_validation: bool = True
    enable_column_drilldown: bool = True
    sample_mismatch_limit: int = Field(default=1000, ge=1)

    # Canonicalization defaults
    trim_whitespace: bool = True
    case_sensitive: bool = True
    null_representations: list[str] = Field(
        default_factory=lambda: ["", "NULL", "null", "None", "NA", "N/A"]
    )
    decimal_precision: Optional[int] = None
    date_format: str = "%Y-%m-%d"
    timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    timezone: str = "UTC"

    class Config:
        env_prefix = "CATEGORY1_"


DEFAULT_PARTITION_COUNTS = [1024, 2048, 4096, 8192]
DEFAULT_CHUNK_SIZES = [1000, 5000, 10000, 50000]
