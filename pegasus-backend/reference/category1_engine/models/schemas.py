# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T10:15:03Z
# --- END GENERATED FILE METADATA ---

"""Data models for reconciliation platform."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DataSourceType(str, Enum):
    TERADATA = "teradata"
    HIVE = "hive"
    ORACLE = "oracle"
    POSTGRES = "postgres"
    SQLSERVER = "sqlserver"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    FILE = "file"


class FileFormat(str, Enum):
    CSV = "csv"
    TSV = "tsv"
    PSV = "psv"
    FIXED_WIDTH = "fixed_width"
    PARQUET = "parquet"
    ORC = "orc"
    AVRO = "avro"
    EXCEL = "excel"


class KeyStrategy(str, Enum):
    PRIMARY = "primary"
    COMPOSITE = "composite"
    BUSINESS = "business"
    USER_DEFINED = "user_defined"
    GENERATED = "generated"
    NONE = "none"


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    precision: Optional[int] = None
    scale: Optional[int] = None
    position: int = 0


class DatasetSchema(BaseModel):
    columns: list[ColumnSchema]
    row_count: Optional[int] = None

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


class SchemaDifference(BaseModel):
    column: str
    difference_type: str  # missing, extra, type_mismatch, nullable_mismatch, precision_mismatch
    source_value: Optional[str] = None
    target_value: Optional[str] = None


class SchemaValidationResult(BaseModel):
    is_valid: bool
    differences: list[SchemaDifference] = Field(default_factory=list)


class ConnectionConfig(BaseModel):
    source_type: DataSourceType
    connection_string: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    schema_name: Optional[str] = None
    table: Optional[str] = None
    query: Optional[str] = None
    file_path: Optional[str] = None
    file_format: Optional[FileFormat] = None
    file_options: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, str] = Field(default_factory=dict)


class ReconciliationJobConfig(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    source: ConnectionConfig
    target: ConnectionConfig
    key_columns: list[str] = Field(default_factory=list)
    key_strategy: KeyStrategy = KeyStrategy.PRIMARY
    compare_columns: Optional[list[str]] = None
    column_mapping: dict[str, str] = Field(default_factory=dict)
    chunk_size: int = 10000
    num_partitions: int = 4096
    memory_limit_mb: int = 1024
    enable_row_count: bool = True
    enable_column_drilldown: bool = True
    canonicalization: dict[str, Any] = Field(default_factory=dict)


class JobStatus(str, Enum):
    PENDING = "pending"
    SCHEMA_VALIDATION = "schema_validation"
    PARTITIONING_SOURCE = "partitioning_source"
    PARTITIONING_TARGET = "partitioning_target"
    RECONCILING = "reconciling"
    DRILLDOWN = "drilldown"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PartitionStats(BaseModel):
    partition_id: int
    source_records: int = 0
    target_records: int = 0
    missing: int = 0
    extra: int = 0
    mismatched: int = 0
    processing_time_ms: float = 0


class ColumnDifference(BaseModel):
    column: str
    source_value: Optional[str] = None
    target_value: Optional[str] = None


class MismatchRecord(BaseModel):
    record_key: str
    partition_id: int
    mismatch_type: str  # missing, extra, changed
    column_differences: list[ColumnDifference] = Field(default_factory=list)
    source_fingerprint: Optional[str] = None
    target_fingerprint: Optional[str] = None


class ExecutionStats(BaseModel):
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0
    source_rows_processed: int = 0
    target_rows_processed: int = 0
    partitions_processed: int = 0
    peak_memory_mb: float = 0
    disk_spill_mb: float = 0
    network_bytes_read: int = 0
    network_bytes_written: int = 0
    chunks_processed: int = 0


class ReconciliationResult(BaseModel):
    job_id: UUID
    status: JobStatus
    schema_validation: Optional[SchemaValidationResult] = None
    source_row_count: Optional[int] = None
    target_row_count: Optional[int] = None
    missing_count: int = 0
    extra_count: int = 0
    mismatched_count: int = 0
    matching_count: int = 0
    partition_stats: list[PartitionStats] = Field(default_factory=list)
    sample_mismatches: list[MismatchRecord] = Field(default_factory=list)
    execution_stats: Optional[ExecutionStats] = None
    error_message: Optional[str] = None


class JobSummary(BaseModel):
    job_id: UUID
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    progress_pct: float = 0
    current_phase: str = ""
