# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T06:13:44Z
# --- END GENERATED FILE METADATA ---

"""Pipeline result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import polars as pl


@dataclass(slots=True)
class SchemaDifference:
    column: str
    difference_type: str
    source_value: str | None = None
    target_value: str | None = None


@dataclass(slots=True)
class ColumnDifference:
    column: str
    source_value: str | None = None
    target_value: str | None = None


@dataclass(slots=True)
class MismatchSample:
    record_key: str
    mismatch_type: str  # missing, extra, changed
    column_differences: list[ColumnDifference] = field(default_factory=list)


@dataclass(slots=True)
class PipelineResult:
    schema_valid: bool = True
    schema_differences: list[SchemaDifference] = field(default_factory=list)
    source_row_count: int = 0
    target_row_count: int = 0
    row_count_match: bool = True
    missing_count: int = 0
    extra_count: int = 0
    changed_count: int = 0
    matching_count: int = 0
    partitions_processed: int = 0
    mismatched_partitions: int = 0
    sample_mismatches: list[MismatchSample] = field(default_factory=list)
    full_mismatches: pl.DataFrame | None = None
    compared_columns: list[str] = field(default_factory=list)
    execution_seconds: float = 0.0
    extra_stats: dict[str, Any] = field(default_factory=dict)
