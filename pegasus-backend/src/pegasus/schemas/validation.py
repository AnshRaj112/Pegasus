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


class LocalPathValidateRequest(BaseModel):
    """JSON body for POST /validate/local (server-side CSV paths)."""

    source_path: str = Field(description="Absolute or user-home path to the expected / golden CSV on the server")
    target_path: str = Field(description="Absolute or user-home path to the actual / candidate CSV on the server")
    uid_column: str = Field(description="Column name to join on (must exist in both files)")
    delimiter: str = Field(
        default="auto",
        description="Field separator: auto, tab, or explicit delimiter (same rules as multipart /validate)",
    )


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


class LocalBrowseRootInfo(BaseModel):
    """One configured PEGASUS_VALIDATION_LOCAL_PATH_ROOTS entry."""

    path: str = Field(description="Configured root path (after expanduser)")
    exists: bool = Field(description="Whether the path currently exists on the server")


class LocalBrowseRootsResponse(BaseModel):
    """Configured browse roots (same allowlist as /validate/local); for UI shortcuts."""

    roots: list[LocalBrowseRootInfo] = Field(default_factory=list)


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
        le=32,
        description=(
            "Maximum number of validation jobs to run in parallel. "
            "Choose based on your available CPU cores (returned by GET /validate/queue). "
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


class QueueStatusResponse(BaseModel):
    """Response for GET /validate/queue."""

    max_concurrency: int = Field(description="Current maximum parallel validation workers")
    cpu_cores_available: int = Field(description="Logical CPU cores detected on the server")
    auto_tune_enabled: bool = Field(description="Whether resource-based auto-tuning is active")
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

