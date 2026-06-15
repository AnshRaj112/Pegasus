# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:10:14Z
# --- END GENERATED FILE METADATA ---

"""Validation run result types (shared by service and tabular pipeline)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pegasus.validation.comparators.models import MismatchReport


@dataclass(slots=True)
class ValidationRunDurations:
    """Timing metadata for a validation job."""

    upload_seconds: float | None = None
    validation_seconds: float | None = None
    total_seconds: float | None = None


@dataclass(slots=True)
class ValidationRunResult:
    """Outcome of a single validation run."""

    report: MismatchReport
    source_row_count: int
    target_row_count: int
    compared_column_count: int
    compared_columns: list[str]
    mismatch_artifact_path: Path | None = None
    mapping_format_checks: list[dict[str, Any]] | None = None
    footer_validation: dict[str, Any] | None = None
    test_mode: str = "full"
    litmus: dict[str, Any] | None = None
    pipeline_metadata: dict[str, Any] | None = None
    durations: ValidationRunDurations | None = None
