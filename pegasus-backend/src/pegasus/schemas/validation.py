# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:32:35Z
# --- END GENERATED FILE METADATA ---

"""Request/response models for the validation API."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

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


class ValidationTestMode(str, Enum):
    """Execution depth for file validation."""

    LITMUS = "litmus"
    FULL = "full"


class LitmusFileStats(BaseModel):
    """Quick structural stats for one compared file."""

    path: str | None = None
    file_name: str | None = None
    file_type: str = "csv"
    size_bytes: int | None = Field(default=None, ge=0)
    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    columns: list[str] = Field(default_factory=list)


class LitmusComparison(BaseModel):
    """Result payload for fast metadata/shape checks."""

    checks_run: list[str] = Field(default_factory=list)
    checks_passed: list[str] = Field(default_factory=list)
    checks_failed: list[str] = Field(default_factory=list)
    source: LitmusFileStats
    target: LitmusFileStats
    notes: list[str] = Field(default_factory=list)


class MismatchCounts(BaseModel):
    """Counts keyed by :class:`MismatchType` string values."""

    missing_in_target: int = Field(ge=0)
    extra_in_target: int = Field(ge=0)
    value_mismatch: int = Field(ge=0, description="Total cell-level value mismatches")
    value_mismatch_rows: int = Field(
        ge=0,
        default=0,
        description="Distinct rows (UIDs) with at least one cell value mismatch",
    )


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
    field_type: str = Field(
        default="text",
        description="Field type: text, integer, float, date, structured (list/dict/tuple literals in the slice)",
    )
    structured_order_sensitive: bool = Field(
        default=False,
        description="When field_type is structured: require element/key order to match between source and target",
    )
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
    compare_enabled: bool = Field(
        default=True,
        description="When false, the field is excluded from value comparison (join key is always used)",
    )
    is_sensitive: bool = Field(
        default=False,
        description="Mask cell values in mismatch reports",
    )
    source_regex_pattern: str | None = Field(
        default=None,
        description="Optional regex applied to the source slice before compare",
    )
    source_regex_replacement: str = Field(default="", description="Replacement for source_regex_pattern")
    target_regex_pattern: str | None = Field(
        default=None,
        description="Optional regex applied to the target slice before compare",
    )
    target_regex_replacement: str = Field(default="", description="Replacement for target_regex_pattern")


class FixedWidthMatchStrategy(str, Enum):
    """How rows are paired when the target file is not in the same order as the source."""

    EXACT = "exact"
    FUZZY = "fuzzy"


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
    match_strategy: FixedWidthMatchStrategy = Field(
        default=FixedWidthMatchStrategy.EXACT,
        description="exact: join key must match; fuzzy: similar keys pair as value mismatches",
    )
    fuzzy_similarity_threshold: float = Field(
        default=0.75,
        ge=0.5,
        le=1.0,
        description="Minimum join-key similarity (0–1) for fuzzy pairing",
    )


class GoogleCloudStorageConfig(BaseModel):
    """Google Cloud Storage object reference plus credentials."""

    provider: Literal["google-cloud-storage"] = Field(
        default="google-cloud-storage",
        description="Only Google Cloud Storage is supported for cloud validation inputs right now.",
    )
    bucket: str | None = Field(default=None, description="GCS bucket name")
    object_name: str = Field(description="Path of the CSV object inside the bucket")
    credentials_json: str | None = Field(
        default=None,
        description="Raw service account JSON string copied from Google Cloud",
    )
    connection_id: UUID | None = Field(
        default=None,
        description="Saved admin-managed cloud connection id (credentials_json may be omitted when set).",
    )
    project_id: str | None = Field(default=None, description="Optional project id override")

    @model_validator(mode="after")
    def _validate_credentials_source(self) -> "GoogleCloudStorageConfig":
        if self.connection_id is None and not (self.credentials_json or "").strip():
            raise ValueError("credentials_json or connection_id is required")
        return self


class LocalPathValidateRequest(BaseModel):
    """JSON body for POST /validate/local (server-side paths)."""

    source_path: str | None = Field(
        default=None,
        description="Absolute or user-home path to the expected / golden file on the server",
    )
    target_path: str | None = Field(
        default=None,
        description="Absolute or user-home path to the actual / candidate file on the server",
    )
    source_cloud: GoogleCloudStorageConfig | None = Field(
        default=None,
        description="Google Cloud Storage source reference used when the source file is not local",
    )
    target_cloud: GoogleCloudStorageConfig | None = Field(
        default=None,
        description="Google Cloud Storage target reference used when the target file is not local",
    )
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
    has_header: bool = Field(
        default=True,
        description=(
            "When false, the first row is data and columns are named column_1, column_2, … "
            "for mapping and UID selection."
        ),
    )
    header_leading_rows: int = Field(
        default=0,
        ge=0,
        le=50,
        description=(
            "Number of physical rows at the start of each file to treat as header/preamble and "
            "exclude from row-level comparison. Applied before has_header."
        ),
    )
    file_format: str = Field(
        default="csv",
        description=(
            "File format: csv, fixed-width, json, parquet, orc, avro, excel, or auto "
            "(multi-layer detection when auto_detect is enabled on the server)"
        ),
    )
    fixed_width_config: FixedWidthConfig | None = Field(
        default=None,
        description="Detailed configuration when file_format is 'fixed-width'",
    )
    json_order_sensitive: bool = Field(
        default=False,
        description=(
            "When file_format is json: require list element order and dict key order to match. "
            "When false, reordered lists and dict keys still match."
        ),
    )
    test_mode: ValidationTestMode = Field(
        default=ValidationTestMode.FULL,
        description=(
            "litmus: full reconciliation with no snippets; fails immediately when row counts differ; "
            "full: full reconciliation with capped mismatch snippets (admin default, user-adjustable)."
        ),
    )
    mismatch_snippet_limit: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description=(
            "Per-category snippet cap for full mode (missing, extra, and per-column value mismatches). "
            "Defaults to the admin-configured value; cannot exceed validation_mismatch_snippet_limit_max."
        ),
    )
    uid_gte: str | None = Field(
        default=None,
        description=(
            "Optional full-test filter: compare only rows where uid_column >= this value "
            "(numeric when possible, otherwise lexical string compare)."
        ),
    )

    @model_validator(mode="after")
    def _validate_storage_inputs(self) -> "LocalPathValidateRequest":
        if self.source_path is None and self.source_cloud is None:
            raise ValueError("source_path or source_cloud is required")
        if self.target_path is None and self.target_cloud is None:
            raise ValueError("target_path or target_cloud is required")
        return self

    @property
    def source_is_cloud(self) -> bool:
        return self.source_cloud is not None

    @property
    def target_is_cloud(self) -> bool:
        return self.target_cloud is not None


class ColumnMapping(BaseModel):
    """Map source column(s) to target column(s) for reconciliation."""

    source_column: str = Field(description="Logical source column name (reporting key and primary source field)")
    target_column: str = Field(
        default="",
        description="Primary target column name (defaults to source_column when empty)",
    )
    source_columns: list[str] | None = Field(
        default=None,
        description="Optional extra source columns for many-to-one mapping (N source -> 1 target)",
    )
    target_columns: list[str] | None = Field(
        default=None,
        description="Optional extra target columns for one-to-many mapping (1 source -> N targets)",
    )
    compare_mode: str = Field(
        default="auto",
        description=(
            "How to compare values: auto (smart dates), text (exact string), "
            "date (calendar date with optional formats), phone (digits only), digits (digits only), "
            "structured (list/dict/tuple literals in cells)"
        ),
    )
    structured_order_sensitive: bool = Field(
        default=False,
        description=(
            "When compare_mode is structured: require list/tuple element order and dict key "
            "order to match. When false, order is ignored but values and spelling must still match."
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
    is_sensitive: bool = Field(
        default=False,
        description="When true, mismatch output values for this column are masked (e.g. ****) to protect PII.",
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


class MismatchPersistenceNote(BaseModel):
    """Recorded when mismatch rows exceed the DB persistence cap."""

    mismatch_rows_persisted: bool
    mismatch_artifact_path: str | None = None
    mismatch_row_cap: int | None = Field(default=None, ge=0)
    validation_job_id: str | None = Field(
        default=None,
        description="Worker job directory id (differs from run_id) for on-disk mismatch NDJSON",
    )


_FOOTER_PERSISTENCE_KEYS = frozenset(
    {"mismatch_rows_persisted", "mismatch_artifact_path", "mismatch_row_cap", "validation_job_id"},
)


def parse_stored_footer_blob(
    raw: dict[str, Any] | None,
) -> tuple[FooterValidationResult | None, MismatchPersistenceNote | None]:
    """Split persisted footer JSON into footer check vs mismatch persistence metadata."""
    if not raw or not isinstance(raw, dict):
        return None, None

    data = dict(raw)
    persistence_raw: dict[str, Any] = {}
    nested = data.pop("_persistence", None)
    if isinstance(nested, dict):
        persistence_raw.update(nested)

    for key in list(_FOOTER_PERSISTENCE_KEYS):
        if key in data:
            persistence_raw[key] = data.pop(key)

    footer_val = FooterValidationResult.model_validate(data) if "match" in data else None
    persistence_val = (
        MismatchPersistenceNote.model_validate(persistence_raw) if persistence_raw else None
    )
    return footer_val, persistence_val


class MappingAnalyzeRequest(BaseModel):
    """JSON body for POST /validate/local/analyze (mapping wizard pre-checks)."""

    source_path: str | None = None
    target_path: str | None = None
    source_cloud: GoogleCloudStorageConfig | None = None
    target_cloud: GoogleCloudStorageConfig | None = None
    uid_column: str
    delimiter: str = "auto"
    column_mappings: list[ColumnMapping] = Field(default_factory=list)
    validate_header_formats: bool = False
    validate_footers: bool = False
    footer_trailing_rows: int = Field(default=1, ge=0, le=10)
    has_header: bool = Field(
        default=True,
        description="When false, files have no header row (columns are column_1, column_2, …).",
    )
    header_leading_rows: int = Field(
        default=0,
        ge=0,
        le=50,
        description="Number of leading rows to skip before sampling/analysis.",
    )

    @model_validator(mode="after")
    def _validate_storage_inputs(self) -> "MappingAnalyzeRequest":
        if self.source_path is None and self.source_cloud is None:
            raise ValueError("source_path or source_cloud is required")
        if self.target_path is None and self.target_cloud is None:
            raise ValueError("target_path or target_cloud is required")
        return self


class MappingAnalyzeResponse(BaseModel):
    """Optional header/footer checks for the mapping UI."""

    format_checks: list[ColumnMappingFormatCheck] = Field(default_factory=list)
    footer_validation: FooterValidationResult | None = None
    delimiter: str = "auto"


class FixedWidthColumnPreview(BaseModel):
    """One inferred or user-edited fixed-width column slice."""

    field_name: str
    source_start: int = Field(ge=0)
    source_end: int = Field(ge=0)
    target_start: int = Field(ge=0)
    target_end: int = Field(ge=0)
    field_type: str = "text"
    width: int = Field(ge=0, default=0, description="Character width (end − start)")
    source_sample: str = ""
    target_sample: str = ""
    date_format: str | None = Field(
        default=None,
        description="Inferred or user-edited friendly date format (e.g. DD/MM/YYYY)",
    )
    source_date_format: str | None = None
    target_date_format: str | None = None
    structured_order_sensitive: bool = False
    compare_enabled: bool = True
    is_sensitive: bool = False
    source_regex_pattern: str | None = None
    source_regex_replacement: str = ""
    target_regex_pattern: str | None = None
    target_regex_replacement: str = ""


class FixedWidthLayoutPreviewResponse(BaseModel):
    """Detected columns and sample lines for the fixed-width mapping UI."""

    columns: list[FixedWidthColumnPreview] = Field(default_factory=list)
    suggested_join_column: str = "record_id"
    source_sample: str = ""
    target_sample: str = ""
    line_width: int = Field(ge=0, default=0)


class JsonParentField(BaseModel):
    """One top-level JSON parent key discovered in a document or NDJSON records."""

    key: str
    value_type: str = Field(description="Coarse JSON type: object, array, string, number, boolean, null")


class JsonParentMappingRow(BaseModel):
    """Suggested or user-edited mapping between source and target JSON parents."""

    source_parent: str | None = None
    target_parent: str | None = None
    ignored: bool = False
    source_type: str | None = None
    target_type: str | None = None


class JsonParentPreviewResponse(BaseModel):
    """Top-level JSON parent keys and auto-suggested mappings for the wizard."""

    document_mode: str = Field(description="document or ndjson")
    source_parents: list[JsonParentField] = Field(default_factory=list)
    target_parents: list[JsonParentField] = Field(default_factory=list)
    suggested_mappings: list[JsonParentMappingRow] = Field(default_factory=list)
    suggested_uid_field: str | None = None


class FileDetectionStageResponse(BaseModel):
    """One layer of the file detection pipeline."""

    detected_type: str
    confidence: int = Field(ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileDetectionResponse(BaseModel):
    """Full multi-layer detection report for a local file."""

    path: str
    file_size_bytes: int = Field(ge=0)
    bytes_read: int = Field(ge=0)
    dataset_model: str
    mime_type: str | None = None
    suggested_file_format: str | None = None
    suggested_delimiter: str | None = None
    warnings: list[str] = Field(default_factory=list)
    extension: FileDetectionStageResponse | None = None
    magic_bytes: FileDetectionStageResponse | None = None
    container: FileDetectionStageResponse | None = None
    compression: FileDetectionStageResponse | None = None
    encoding: FileDetectionStageResponse | None = None
    text_binary: FileDetectionStageResponse | None = None
    structured_format: FileDetectionStageResponse | None = None
    schema_hint: FileDetectionStageResponse | None = Field(
        default=None,
        serialization_alias="schema",
        validation_alias="schema",
    )
    validation_strategy: FileDetectionStageResponse | None = None


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
    has_header: bool = Field(
        default=True,
        description="Whether the first row was treated as column names",
    )
    inferred_has_header: bool | None = Field(
        default=None,
        description="Heuristic guess from the first physical row (both files must look like headers)",
    )
    source_samples: dict[str, list[str]] = Field(
        default_factory=dict,
        description="First sample rows per source column (string values) for mapping preview",
    )
    target_samples: dict[str, list[str]] = Field(
        default_factory=dict,
        description="First sample rows per target column (string values) for mapping preview",
    )
    sample_row_count: int = Field(
        default=6,
        ge=1,
        le=20,
        description="Number of data rows included in source_samples / target_samples",
    )
    complex_columns: list[str] = Field(
        default_factory=list,
        description="Compared columns whose sample cells contain list/dict/tuple literals",
    )
    needs_order_preference: bool = Field(
        default=False,
        description="True when complex_columns is non-empty; client may ask about order sensitivity",
    )


class LocalBrowseRootInfo(BaseModel):
    """One configured PEGASUS_VALIDATION_LOCAL_PATH_ROOTS entry."""

    path: str = Field(description="Configured root path (after expanduser)")
    exists: bool = Field(description="Whether the path currently exists on the server")


class LocalBrowseRootsResponse(BaseModel):
    """Configured browse roots (same allowlist as /validate/local); for UI shortcuts."""

    roots: list[LocalBrowseRootInfo] = Field(default_factory=list)


class LocalPathBrowseConfigResponse(BaseModel):
    """Server-local path picker defaults (host/container remap for Docker)."""

    default_browse_path: str = Field(
        description="Directory used when browse is opened without a path (display form)",
    )
    path_remap_enabled: bool = Field(
        description="True when host and container path prefixes are configured",
    )
    host_path_prefix: str | None = Field(
        default=None,
        description="Host-side path prefix shown in the UI when remap is enabled",
    )
    container_path_prefix: str | None = Field(
        default=None,
        description="In-container mount path paired with host_path_prefix",
    )


class ValidationOptionsResponse(BaseModel):
    """Public validation wizard options (snippet caps and supported test modes)."""

    test_modes: list[ValidationTestMode] = Field(
        default_factory=lambda: [
            ValidationTestMode.LITMUS,
            ValidationTestMode.FULL,
        ],
        description="Test modes exposed in the validation wizard.",
    )
    mismatch_snippet_limit_default: int = Field(ge=1, le=50)
    mismatch_snippet_limit_max: int = Field(ge=1, le=50)


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
    test_mode: ValidationTestMode = Field(
        default=ValidationTestMode.FULL,
        description="Validation depth used for this run.",
    )
    litmus: LitmusComparison | None = Field(
        default=None,
        description="Present when test_mode is litmus.",
    )
    pipeline_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Category-1 six-stage pipeline metrics (partition counts, timings, etc.).",
    )


class ValidationJobAcceptedResponse(BaseModel):
    """Returned immediately when a validation job is accepted (queued or already running)."""

    job_id: UUID
    status: str = Field(
        default="queued",
        description="queued when waiting for a worker slot; running when started immediately",
    )
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



class BatchFailureMode(str, Enum):
    """How to proceed when one validation unit fails in a batch job."""

    STOP = "stop"
    CONTINUE = "continue"


class ValidationUnitSpec(BaseModel):
    """One logical source/target comparison (may merge multiple paths per side)."""

    unit_id: str = Field(description="Stable id for UI pairing and per-pair column mapping")
    source_paths: list[str] = Field(min_length=1, description="One or more source files (merged when >1)")
    target_paths: list[str] = Field(min_length=1, description="One or more target files (merged when >1)")
    uid_column: str = Field(default="id", description="Join column for CSV validation")
    column_mappings: list[ColumnMapping] = Field(default_factory=list)
    fixed_width_config: FixedWidthConfig | None = Field(
        default=None,
        description="Per-pair fixed-width layout when file_format is fixed-width",
    )


class LocalBatchValidateRequest(BaseModel):
    """JSON body for POST /validate/local/batch."""

    file_format: str = Field(default="csv", description="csv, fixed-width, or json")
    units: list[ValidationUnitSpec] = Field(min_length=1)
    on_unit_failure: BatchFailureMode = Field(
        default=BatchFailureMode.CONTINUE,
        description="stop after first failed unit, or run all units and report per-pair status",
    )
    delimiter: str = Field(default="auto")
    has_header: bool = Field(default=True)
    header_leading_rows: int = Field(default=0, ge=0, le=50)
    validate_header_formats: bool = Field(default=False)
    validate_footers: bool = Field(default=False)
    footer_trailing_rows: int = Field(default=1, ge=0, le=10)
    cloud_bucket: str | None = Field(
        default=None,
        description="When set, unit source_paths/target_paths are object names in this bucket",
    )
    cloud_credentials_json: str | None = Field(
        default=None,
        description="Service account JSON used with cloud_bucket for batch jobs",
    )
    cloud_project_id: str | None = None
    test_mode: ValidationTestMode = Field(default=ValidationTestMode.FULL)
    uid_gte: str | None = None


class MatchFilePairsRequest(BaseModel):
    """JSON body for POST /validate/local/match-pairs."""

    source_directory: str
    target_directory: str
    file_format: str = Field(default="csv", description="Used to filter files by extension")
    recursive: bool = Field(
        default=False,
        description="When true, include files in subdirectories (matched by basename only)",
    )


class CloudBrowseRequest(BaseModel):
    """JSON body for POST /validate/cloud/browse."""

    bucket: str | None = None
    prefix: str = Field(default="", description="Folder prefix inside the bucket (e.g. data/2024/)")
    credentials_json: str | None = None
    connection_id: UUID | None = None
    project_id: str | None = None
    file_format: str = Field(default="csv")

    @model_validator(mode="after")
    def _validate_cloud_auth(self) -> "CloudBrowseRequest":
        if self.connection_id is None and not (self.credentials_json or "").strip():
            raise ValueError("credentials_json or connection_id is required")
        return self


class CloudBrowseEntry(BaseModel):
    """One prefix or object under a GCS browse listing."""

    name: str
    path: str = Field(description="Object name or prefix path within the bucket")
    is_dir: bool
    size_bytes: int | None = Field(
        default=None,
        ge=0,
        description="Object size from GCS metadata (files only; omitted for prefixes)",
    )
    created_at: str | None = Field(
        default=None,
        description="Object creation time from GCS metadata (files only)",
    )
    updated_at: str | None = Field(
        default=None,
        description="Object last-modified time from GCS metadata (files only)",
    )
    owner: str | None = Field(
        default=None,
        description="Object owner entity from GCS metadata or custom metadata",
    )
    created_by: str | None = Field(
        default=None,
        description="Creator from GCS custom object metadata when present",
    )


class CloudBrowseResponse(BaseModel):
    """GCS prefix listing for the cloud file picker."""

    bucket: str
    prefix: str
    parent_prefix: str | None = None
    entries: list[CloudBrowseEntry] = Field(default_factory=list)
    truncated: bool = False


class CloudFileProfileRequest(BaseModel):
    """JSON body for POST /validate/cloud/profile."""

    cloud: GoogleCloudStorageConfig
    delimiter: str = Field(default="auto", description="Field separator or auto")
    has_header: bool = Field(
        default=True,
        description="Whether the first row contains column names",
    )


class CloudFileProfileResponse(BaseModel):
    """Detected format and shape stats for one GCS object."""

    object_name: str
    gcs_uri: str
    file_size_bytes: int = Field(ge=0)
    file_format: str = Field(description="Detected format label (csv, fixed-width, parquet, …)")
    suggested_file_format: str | None = None
    dataset_model: str | None = None
    column_count: int = Field(ge=0)
    row_count: int = Field(ge=0)
    delimiter: str | None = None
    has_header: bool = True
    json_preview: str | None = Field(
        default=None,
        description="Pretty-printed JSON prefix for overview preview (JSON documents only).",
    )


class CloudMatchFilePairsRequest(BaseModel):
    """JSON body for POST /validate/cloud/match-pairs."""

    bucket: str | None = None
    source_prefix: str = ""
    target_prefix: str = ""
    credentials_json: str | None = None
    connection_id: UUID | None = None
    project_id: str | None = None
    file_format: str = Field(default="csv")
    recursive: bool = False

    @model_validator(mode="after")
    def _validate_cloud_auth(self) -> "CloudMatchFilePairsRequest":
        if self.connection_id is None and not (self.credentials_json or "").strip():
            raise ValueError("credentials_json or connection_id is required")
        return self


class FilePairMatch(BaseModel):
    """One suggested or user-confirmed file pair."""

    unit_id: str
    source_path: str
    target_path: str
    source_name: str
    target_name: str
    auto_matched: bool = Field(default=True)


class MatchFilePairsResponse(BaseModel):
    """Auto filename pairing between two directories."""

    pairs: list[FilePairMatch] = Field(default_factory=list)
    unmatched_sources: list[str] = Field(default_factory=list)
    unmatched_targets: list[str] = Field(default_factory=list)


class BatchUnitResult(BaseModel):
    """Outcome for one unit in a batch validation job."""

    unit_id: str
    source_paths: list[str] = Field(default_factory=list)
    target_paths: list[str] = Field(default_factory=list)
    status: str = Field(description="completed | failed | skipped")
    error: str | None = None
    result: ValidateResponse | None = None


class BatchValidateSummary(BaseModel):
    """Aggregate stats across all units in a batch job."""

    total_units: int = Field(ge=0)
    completed_units: int = Field(ge=0)
    failed_units: int = Field(ge=0)
    skipped_units: int = Field(ge=0)
    passed_units: int = Field(ge=0, description="Units with zero mismatch records")
    is_match: bool = Field(description="True when every completed unit has zero mismatches")


class BatchValidateResponse(BaseModel):
    """Final payload for a completed batch validation job."""

    summary: BatchValidateSummary
    units: list[BatchUnitResult] = Field(default_factory=list)
    on_unit_failure: BatchFailureMode = BatchFailureMode.CONTINUE
    durations: ValidationDurations | None = None


class ValidationJobDetailResponse(BaseModel):
    """Poll response: while running only *status* is set; when completed *result* contains the API payload."""

    status: str
    phase: str | None = None
    message: str | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    result: ValidateResponse | None = None
    batch_result: BatchValidateResponse | None = Field(
        default=None,
        description="Present when the job was queued via POST /validate/local/batch",
    )
    resource_profile: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Memory, disk, and CPU footprint snapshots captured before, during, and after validation. "
            "Includes peak RSS, job workspace disk usage, and CPU utilization samples."
        ),
    )


def build_mismatch_counts(
    summary_dict: dict[str, int],
    *,
    value_mismatch_rows: int | None = None,
) -> MismatchCounts:
    """Normalize raw summary dict into a typed model with defaults."""
    return MismatchCounts(
        missing_in_target=int(summary_dict.get(MismatchType.MISSING_IN_TARGET.value, 0)),
        extra_in_target=int(summary_dict.get(MismatchType.EXTRA_IN_TARGET.value, 0)),
        value_mismatch=int(summary_dict.get(MismatchType.VALUE_MISMATCH.value, 0)),
        value_mismatch_rows=int(value_mismatch_rows or 0),
    )


class UpdateQueueSettingsRequest(BaseModel):
    """JSON body for PATCH /validate/queue — lets users tune concurrency at runtime."""

    max_concurrency: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum parallel validation jobs. "
            "Running jobs are never killed; the new limit affects when queued jobs start."
        ),
    )
    auto_tune_enabled: bool | None = Field(
        default=None,
        description=(
            "When true, every job that fits current resources starts immediately; "
            "the rest wait in the FIFO queue. When false, only max_concurrency is used "
            "(0 falls back to CPU core count)."
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

    max_concurrency: int = Field(
        description="User-set parallel cap (0 = no fixed cap; resource advisor decides)"
    )
    effective_max_concurrency: int = Field(
        description=(
            "Parallel slots the drain loop uses right now "
            "(resource recommendation when auto-tune is on and max_concurrency is 0)"
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

