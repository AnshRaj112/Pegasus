"""Structured mismatch report types for UID-based comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import polars as pl


class MismatchType(StrEnum):
    """High-level classification of a mismatch row."""

    MISSING_IN_TARGET = "missing_in_target"
    """Row exists in *source* but no row with the same UID in *target*."""

    EXTRA_IN_TARGET = "extra_in_target"
    """Row exists in *target* but no row with the same UID in *source*."""

    VALUE_MISMATCH = "value_mismatch"
    """Same UID in both frames but at least one compared column differs (incl. null vs value)."""


MISMATCH_REPORT_SCHEMA: dict[str, pl.DataType] = {
    "uid": pl.String,
    "mismatch_type": pl.String,
    "column_name": pl.String,
    "source_value": pl.String,
    "target_value": pl.String,
    "row_detail": pl.String,
}


def empty_mismatch_frame() -> pl.DataFrame:
    """Return an empty frame with the canonical mismatch schema."""
    return pl.DataFrame(schema=MISMATCH_REPORT_SCHEMA)


@dataclass(slots=True)
class MismatchReport:
    """Structured result of comparing two frames on a shared UID column.

    Attributes
    ----------
    mismatches
        Long-form table; one row per reported mismatch (see ``MismatchType``).
    summary
        Aggregate counts keyed by ``MismatchType`` value strings.
    mismatch_artifact_path
        When set, full mismatch rows were streamed to this NDJSON file and
        ``mismatches`` may be empty to avoid holding the full report in RAM.
    """

    mismatches: pl.DataFrame
    summary: dict[str, int] = field(default_factory=dict)
    mismatch_artifact_path: Path | None = None

    def row_dicts(self) -> list[dict[str, Any]]:
        """Serialize mismatches as plain dicts (materializes the frame)."""
        if self.mismatches.is_empty():
            return []
        return self.mismatches.to_dicts()
