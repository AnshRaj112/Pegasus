"""API models for persisted validation history."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from pegasus.schemas.validation import (
    ColumnMapping,
    ColumnMappingFormatCheck,
    FooterValidationResult,
    MismatchCounts,
    ValidationDurations,
)


class ValidationHistorySummary(BaseModel):
    """One row in the validation history list."""

    run_id: UUID
    status: str
    source_path: str | None = None
    target_path: str | None = None
    source_filename: str | None = None
    target_filename: str | None = None
    uid_column: str
    delimiter: str
    is_match: bool | None = None
    mismatch_counts: MismatchCounts
    mapping_count: int = Field(ge=0, description="Number of source→target column mappings used")
    durations: ValidationDurations = Field(default_factory=ValidationDurations)
    created_at: datetime
    completed_at: datetime | None = None


class ValidationDailyStatRow(BaseModel):
    """Passed vs failed validation counts for one day (by ``completed_at``)."""

    date: date
    passed: int = Field(ge=0, description="Completed runs with full data match")
    failed: int = Field(ge=0, description="Failed runs or completed with mismatches")
    total: int = Field(ge=0)


class ValidationDailyTotals(BaseModel):
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    total: int = Field(ge=0)


class ValidationDailyStatsResponse(BaseModel):
    items: list[ValidationDailyStatRow] = Field(default_factory=list)
    totals: ValidationDailyTotals


class ValidationHistoryListResponse(BaseModel):
    """Paginated validation history."""

    items: list[ValidationHistorySummary] = Field(default_factory=list)
    total: int = Field(ge=0)
    file_pair_key: str | None = Field(
        default=None,
        description="Present when filtered by source_path + target_path",
    )


class ValidationHistoryDetail(ValidationHistorySummary):
    """Full persisted record for one validation run."""

    column_mappings: list[ColumnMapping] = Field(default_factory=list)
    compared_columns: list[str] = Field(default_factory=list)
    mapping_format_checks: list[ColumnMappingFormatCheck] = Field(default_factory=list)
    footer_validation: FooterValidationResult | None = None
    validate_header_formats: bool = False
    validate_footers: bool = False
    source_row_count: int | None = Field(default=None, ge=0)
    target_row_count: int | None = Field(default=None, ge=0)
    compared_column_count: int | None = Field(default=None, ge=0)
    error_detail: str | None = None


class ValidationHistoryMismatchRow(BaseModel):
    """One mismatch row from the database."""

    uid: str
    mismatch_type: str
    column_name: str | None = None
    source_value: str | None = None
    target_value: str | None = None
    row_detail: str | None = None


class ValidationHistoryMismatchesResponse(BaseModel):
    """Paginated mismatch rows for a historical run."""

    run_id: UUID
    items: list[ValidationHistoryMismatchRow] = Field(default_factory=list)
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)


class SaveDraftRequest(BaseModel):
    """Payload to save a mapping draft in history."""

    source_path: str = Field(description="Source CSV file path")
    target_path: str = Field(description="Target CSV file path")
    uid_column: str = Field(description="Join key column")
    delimiter: str = Field(default="auto", description="Delimiter")
    column_mappings: list[ColumnMapping] = Field(default_factory=list, description="Column mappings")
    validate_header_formats: bool = Field(default=False, description="Header formats validation flag")
    validate_footers: bool = Field(default=False, description="Footers validation flag")

