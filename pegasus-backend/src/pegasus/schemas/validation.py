"""Request/response models for the validation API."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from pegasus.validation.comparators.models import MismatchType


class MismatchSampleRow(BaseModel):
    """One row in the long-form mismatch report."""

    uid: str = Field(description="Business UID that triggered the mismatch")
    mismatch_type: str = Field(
        description="missing_in_target | extra_in_target | value_mismatch",
    )
    column_name: str | None = Field(
        default=None,
        description="Compared column for value_mismatch; null for row presence issues",
    )
    source_value: str | None = Field(
        default=None,
        description="Serialized source cell; null when not applicable",
    )
    target_value: str | None = Field(
        default=None,
        description="Serialized target cell; null when not applicable",
    )
    row_detail: dict[str, Any] | None = Field(
        default=None,
        description="Optional JSON object with source_record and/or target_record (full CSV rows)",
    )

    @field_validator("row_detail", mode="before")
    @classmethod
    def _parse_row_detail(cls, value: object) -> dict[str, Any] | None:
        if value is None or value == "":
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
        return None


class ValidationSummary(BaseModel):
    """High-level stats for the compared files."""

    source_row_count: int = Field(ge=0)
    target_row_count: int = Field(ge=0)
    compared_column_count: int = Field(
        ge=0,
        description="Shared non-UID columns considered in value comparison",
    )
    total_mismatch_records: int = Field(
        ge=0,
        description="Rows in the long-form mismatch table (one per column diff or presence issue)",
    )
    is_match: bool = Field(description="True when there are zero mismatch records")


class MismatchCounts(BaseModel):
    """Counts keyed by :class:`MismatchType` string values."""

    missing_in_target: int = Field(ge=0)
    extra_in_target: int = Field(ge=0)
    value_mismatch: int = Field(ge=0)


class MismatchSampleGroups(BaseModel):
    """Mismatch rows split by category (missing/extra are complete up to the presence cap)."""

    missing_in_target: list[MismatchSampleRow] = Field(default_factory=list)
    extra_in_target: list[MismatchSampleRow] = Field(default_factory=list)
    value_mismatch: list[MismatchSampleRow] = Field(default_factory=list)


class FixedWidthField(BaseModel):
    """Configuration for one mapped fixed-width field slice."""

    field_name: str = Field(description="Name of the field")
    source_start: int = Field(ge=0, description="0-indexed start position in source line")
    source_end: int = Field(ge=0, description="0-indexed end position in source line")
    target_start: int = Field(ge=0, description="0-indexed start position in target line")
    target_end: int = Field(ge=0, description="0-indexed end position in target line")
    field_type: str = Field(default="text", description="Field type: text, integer, float, date")
    date_format: str | None = Field(
        default=None,
        description="Optional strptime/friendly format if field_type is date (used for both sides when source/target formats omitted)",
    )
    source_date_format: str | None = Field(
        default=None,
        description="Source-side date format when field_type is date (overrides date_format)",
    )
    target_date_format: str | None = Field(
        default=None,
        description="Target-side date format when field_type is date (overrides date_format)",
    )


class FixedWidthConfig(BaseModel):
    """Configuration for fixed-width validation."""

    source_date_start: int | None = Field(default=None, ge=0, description="0-indexed start position of source date")
    source_date_end: int | None = Field(default=None, ge=0, description="0-indexed end position of source date")
    source_date_format: str | None = Field(default=None, description="Strptime format of source date")
    target_date_start: int | None = Field(default=None, ge=0, description="0-indexed start position of target date")
    target_date_end: int | None = Field(default=None, ge=0, description="0-indexed end position of target date")
    target_date_format: str | None = Field(default=None, description="Strptime format of target date")

    uid_column: str | None = Field(default=None, description="Join key column name")
    uid_source_start: int | None = Field(default=None, ge=0, description="0-indexed start of source join key")
    uid_source_end: int | None = Field(default=None, ge=0, description="0-indexed end of source join key")
    uid_target_start: int | None = Field(default=None, ge=0, description="0-indexed start of target join key")
    uid_target_end: int | None = Field(default=None, ge=0, description="0-indexed end of target join key")
    fields: list[FixedWidthField] = Field(default_factory=list, description="List of fields to validate")


class LocalPathValidateRequest(BaseModel):
    """JSON body for POST /validate/local (server-side paths)."""

    source_path: str = Field(description="Absolute or user-home path to the expected / golden file on the server")
    target_path: str = Field(description="Absolute or user-home path to the actual / candidate file on the server")
    uid_column: str = Field(default="line", description="Column name to join on (must exist in both CSV files, ignored for fixed-width)")
    column_mappings: list[ColumnMapping] = Field(
        default_factory=list,
        description=(
            "Optional source->target column mappings used when header names differ. "
            "Each mapped target column is renamed to the source column name before comparison."
        ),
    )
    delimiter: str = Field(
        default="auto",
        description="Field separator: auto, tab, or explicit delimiter (ignored for fixed-width)",
    )
    validate_header_formats: bool = Field(
        default=False,
        description="When true, infer formats on mapped columns and attach compatibility checks to the result.",
    )
    validate_footers: bool = Field(
        default=False,
        description="When true, compare trailing rows between source and target files.",
    )
    footer_trailing_rows: int = Field(
        default=1,
        ge=0,
        le=10,
        description="Number of trailing physical rows to treat as footer when validate_footers is true.",
    )
    file_format: str = Field(default="csv", description="File format type: 'csv' or 'fixed-width'")
    fixed_width_config: FixedWidthConfig | None = Field(default=None, description="Detailed configuration when file_format is 'fixed-width'")


class ColumnMapping(BaseModel):
    """Pair one source column name with the corresponding target column name."""

    source_column: str = Field(description="Source column name to validate")
    target_column: str = Field(description="Target column name to compare against the source column")
    compare_mode: str = Field(
        default="auto",
        description=(
            "How to compare values: auto (smart dates), text (exact string), "
            "date (calendar date with optional formats), phone (digits only), digits (digits only)"
        ),
    )
    source_date_format: str | None = Field(
        default=None,
        description="strptime/friendly date format for source when compare_mode is date",
    )
    target_date_format: str | None = Field(
        default=None,
        description="strptime/friendly date format for target when compare_mode is date",
    )
    source_strip_prefix: str | None = Field(
        default=None,
        description="Remove this prefix from source values before compare (e.g. +91)",
    )
    target_strip_prefix: str | None = Field(
        default=None,
        description="Remove this prefix from target values before compare",
    )
    source_regex_pattern: str | None = Field(
        default=None,
        description="Optional regex applied to source value before compare",
    )
    source_regex_replacement: str = Field(default="", description="Replacement for source_regex_pattern")
    target_regex_pattern: str | None = Field(
        default=None,
        description="Optional regex applied to target value before compare",
    )
    target_regex_replacement: str = Field(default="", description="Replacement for target_regex_pattern")


class LocalBrowseEntry(BaseModel):
    """One file or directory under GET /validate/local/browse."""

    name: str
    path: str
    is_dir: bool


class LocalBrowseResponse(BaseModel):
    """Directory listing for the local-path file picker UI."""

    path: str = Field(description="Absolute resolved directory that was listed")
    parent_path: str | None = Field(
        default=None,
        description="Absolute parent directory if the UI may navigate up; null at an allowed root",
    )
    entries: list[LocalBrowseEntry] = Field(
        default_factory=list,
        description="Sorted entries (directories first, then files); symlinks outside allowed roots are omitted",
    )
    truncated: bool = Field(
        default=False,
        description="True when the directory had more children than the server returns (see cap in API docs)",
    )


class ColumnMappingFormatCheck(BaseModel):
    """Format compatibility for one source→target column mapping."""

    source_column: str
    target_column: str
    source_format: str
    target_format: str
    source_confidence: float = Field(ge=0, le=1)
    target_confidence: float = Field(ge=0, le=1)
    compatible: bool
    message: str | None = None
    source_example: str | None = None
    target_example: str | None = None


class FooterValidationResult(BaseModel):
    """Outcome of comparing trailing rows between source and target files."""

    enabled: bool = True
    match: bool
    source_trailing_rows: list[list[str]] = Field(default_factory=list)
    target_trailing_rows: list[list[str]] = Field(default_factory=list)
    message: str | None = None


class MappingAnalyzeRequest(BaseModel):
    """JSON body for POST /validate/local/analyze (mapping wizard pre-checks)."""

    source_path: str
    target_path: str
    uid_column: str
    delimiter: str = "auto"
    column_mappings: list[ColumnMapping] = Field(default_factory=list)
    validate_header_formats: bool = False
    validate_footers: bool = False
    footer_trailing_rows: int = Field(default=1, ge=0, le=10)


class MappingAnalyzeResponse(BaseModel):
    """Optional header/footer checks for the mapping UI."""

    format_checks: list[ColumnMappingFormatCheck] = Field(default_factory=list)
    footer_validation: FooterValidationResult | None = None
    delimiter: str = "auto"


class LocalColumnPreviewResponse(BaseModel):
    """Header preview for the local-path mapping UI."""

    source_columns: list[str] = Field(default_factory=list, description="All source columns, including the UID column")
    target_columns: list[str] = Field(default_factory=list, description="All target columns, including the UID column")
    compare_columns: list[str] = Field(
        default_factory=list,
        description="Source columns available for value comparison after removing the selected UID column",
    )
    auto_mappings: list[dict] = Field(
        default_factory=list,
        description="Exact name matches discovered automatically from source and target headers",
    )
    unmatched_source_columns: list[str] = Field(
        default_factory=list,
        description="Source columns with no automatic target match",
    )
    unmatched_target_columns: list[str] = Field(
        default_factory=list,
        description="Target columns with no automatic source match",
    )
    delimiter: str = Field(description="Resolved delimiter used to read the headers")


class LocalBrowseRootInfo(BaseModel):
    """One configured PEGASUS_VALIDATION_LOCAL_PATH_ROOTS entry."""

    path: str = Field(description="Configured root path (after expanduser)")
    exists: bool = Field(description="Whether the path currently exists on the server")


class LocalBrowseRootsResponse(BaseModel):
    """Configured browse roots (same allowlist as /validate/local); for UI shortcuts."""

    roots: list[LocalBrowseRootInfo] = Field(default_factory=list)


class ValidationDurations(BaseModel):
    """Upload, validation, and total wall-clock seconds for a completed job."""

    upload_seconds: float | None = Field(default=None, ge=0)
    validation_seconds: float | None = Field(default=None, ge=0)
    total_seconds: float | None = Field(default=None, ge=0)


class ValidateResponse(BaseModel):
    """Response body for POST /validate."""

    summary: ValidationSummary
    mismatch_counts: MismatchCounts
    mismatch_sample_groups: MismatchSampleGroups = Field(
        default_factory=MismatchSampleGroups,
        description=(
            "Missing/extra rows (with source_record / target_record in row_detail when available) up to "
            "PEGASUS_VALIDATION_PRESENCE_MISMATCH_RESPONSE_MAX_ROWS per side; value_mismatch obeys "
            "PEGASUS_VALIDATION_MISMATCH_SAMPLE_LIMIT."
        ),
    )
    value_mismatch_by_column: dict[str, int] = Field(
        default_factory=dict,
        description="Total value_mismatch row counts per compared column (full report, not just samples)",
    )
    compared_columns: list[str] = Field(
        default_factory=list,
        description="Shared non-UID column names that were compared (order is stable for UI grouping)",
    )
    run_id: UUID | None = Field(
        default=None,
        description="Database id of the persisted run when PEGASUS_ENABLE_VALIDATION_PERSISTENCE is true",
    )
    value_mismatch_by_column_omitted: bool = Field(
        default=False,
        description=(
            "True when per-column value_mismatch_by_column was skipped because value_mismatch "
            "row count exceeded validation_value_mismatch_column_stats_max_rows (saves memory)."
        ),
    )
    mapping_format_checks: list[ColumnMappingFormatCheck] = Field(
        default_factory=list,
        description="Present when validate_header_formats was true on the request.",
    )
    footer_validation: FooterValidationResult | None = Field(
        default=None,
        description="Present when validate_footers was true on the request.",
    )
    durations: ValidationDurations | None = Field(
        default=None,
        description="Wall-clock timings when available from the validation worker.",
    )


class ValidationJobAcceptedResponse(BaseModel):
    """Returned immediately when a validation job is queued (processing runs in a subprocess)."""

    job_id: UUID
    status: str = Field(default="queued", description="queued until the worker picks up the job directory")
    poll_url: str = Field(description="Relative URL to poll for status and the final ValidateResponse payload")
    queue_position: int | None = Field(
        default=None,
        description="0-based position in the queue (0 = next to run); null when already running",
    )
    queue_pending: int | None = Field(
        default=None,
        description="Total number of jobs waiting in the queue (including this one)",
    )
    queue_running: int | None = Field(
        default=None,
        description="Number of validation jobs currently executing",
    )
    max_concurrency: int | None = Field(
        default=None,
        description="Configured maximum number of parallel validation workers",
    )


class ValidationJobDetailResponse(BaseModel):
    """Poll response: while running only *status* is set; when completed *result* contains the API payload."""

    status: str
    phase: str | None = None
    message: str | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    result: ValidateResponse | None = None


def build_mismatch_counts(summary_dict: dict[str, int]) -> MismatchCounts:
    """Normalize raw summary dict into a typed model with defaults."""
    return MismatchCounts(
        missing_in_target=int(summary_dict.get(MismatchType.MISSING_IN_TARGET.value, 0)),
        extra_in_target=int(summary_dict.get(MismatchType.EXTRA_IN_TARGET.value, 0)),
        value_mismatch=int(summary_dict.get(MismatchType.VALUE_MISMATCH.value, 0)),
    )


class UpdateQueueSettingsRequest(BaseModel):
    """JSON body for PATCH /validate/queue — lets users tune concurrency at runtime."""

    max_concurrency: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum number of validation jobs to run in parallel (user upper cap). "
            "Use GET /validate/queue resource_advisor for RAM/disk/CPU-based guidance. "
            "Running jobs are never killed; the new limit affects when queued jobs start."
        ),
    )
    auto_tune_enabled: bool | None = Field(
        default=None,
        description=(
            "When true, the system dynamically caps effective concurrency below "
            "max_concurrency if RAM, disk, or swap pressure is too high. "
            "When false, only the user-set max_concurrency is used."
        ),
    )
    threads_per_job: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Threads/processes for partition comparison inside each validation worker. "
            "0 = auto (all logical CPUs for that worker)."
        ),
    )
    disk_headroom_multiplier: float | None = Field(
        default=None,
        ge=1.0,
        le=10.0,
        description=(
            "Disk safety factor per job: required free bytes >= multiplier × (source + target CSV size) "
            "before spill/sort."
        ),
    )


class QueueStatusResponse(BaseModel):
    """Response for GET /validate/queue."""

    max_concurrency: int = Field(description="User-set maximum parallel validation workers")
    effective_max_concurrency: int = Field(
        description=(
            "Effective parallel cap used by the drain loop "
            "(min of max_concurrency and resource advisor when auto-tune is on)"
        ),
    )
    cpu_cores_available: int = Field(description="Logical CPU cores detected on the server")
    auto_tune_enabled: bool = Field(description="Whether resource-based auto-tuning is active")
    threads_per_job: int = Field(
        description="Configured worker threads per validation job (0 = auto / all cores)"
    )
    disk_headroom_multiplier: float = Field(
        description="Configured disk headroom multiplier per validation job"
    )
    effective_threads_per_job: int = Field(
        description="Resolved thread cap used when a worker starts (after auto=host cores)"
    )
    pending: int = Field(description="Jobs waiting in the queue")
    running: int = Field(description="Jobs currently executing")
    finished: int = Field(description="Completed/failed jobs still tracked in memory")
    total_tracked: int = Field(description="Total jobs tracked in memory")
    resource_advisor: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Live resource snapshot: system RAM/disk/swap stats, per-job estimates, "
            "safe limits (max_safe_by_ram, max_safe_by_disk, max_safe_by_cpu), "
            "and the system-recommended max_concurrency."
        ),
    )
    jobs: list[dict[str, Any]] = Field(default_factory=list, description="Recent job snapshots")

