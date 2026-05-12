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
    """Sample mismatch rows split by category (each list obeys the global sample budget)."""

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


class ValidateResponse(BaseModel):
    """Response body for POST /validate."""

    summary: ValidationSummary
    mismatch_counts: MismatchCounts
    mismatch_sample_groups: MismatchSampleGroups = Field(
        default_factory=MismatchSampleGroups,
        description="Sample rows per mismatch category (see validation_mismatch_sample_limit)",
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
