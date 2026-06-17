# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:51:18Z
# --- END GENERATED FILE METADATA ---

"""Structured mismatch report types (retained for API/history compatibility)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import polars as pl


class MismatchType(StrEnum):
    MISSING_IN_TARGET = "missing_in_target"
    EXTRA_IN_TARGET = "extra_in_target"
    VALUE_MISMATCH = "value_mismatch"


MISMATCH_REPORT_SCHEMA: dict[str, pl.DataType] = {
    "uid": pl.String,
    "mismatch_type": pl.String,
    "column_name": pl.String,
    "source_value": pl.String,
    "target_value": pl.String,
    "row_detail": pl.String,
}


def empty_mismatch_frame() -> pl.DataFrame:
    return pl.DataFrame(schema=MISMATCH_REPORT_SCHEMA)


@dataclass(slots=True)
class MismatchReport:
    mismatches: pl.DataFrame
    summary: dict[str, int] = field(default_factory=dict)
    mismatch_artifact_path: Path | None = None

    def row_dicts(self) -> list[dict[str, Any]]:
        if self.mismatches.is_empty():
            return []
        return self.mismatches.to_dicts()
