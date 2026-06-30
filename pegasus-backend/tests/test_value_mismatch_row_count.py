# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:42:20Z
# --- END GENERATED FILE METADATA ---

"""Tests for value mismatch row counting."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import polars as pl

from pegasus.repositories.validation_repository import _value_mismatch_row_count
from pegasus.validation.comparators.models import MismatchType


def test_value_mismatch_row_count_dedupes_uids_in_frame() -> None:
    frame = pl.DataFrame({
        "uid": ["a", "a", "b"],
        "mismatch_type": [
            MismatchType.VALUE_MISMATCH.value,
            MismatchType.VALUE_MISMATCH.value,
            MismatchType.VALUE_MISMATCH.value,
        ],
        "column_name": ["c1", "c2", "c1"],
    })
    assert _value_mismatch_row_count(mismatches=frame, artifact=None) == 2


def test_value_mismatch_row_count_reads_ndjson_artifact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifact = Path(tmp) / "mismatches.ndjson"
        with artifact.open("w", encoding="utf-8") as fp:
            for row in (
                {"uid": "x", "mismatch_type": MismatchType.VALUE_MISMATCH.value, "column_name": "a"},
                {"uid": "x", "mismatch_type": MismatchType.VALUE_MISMATCH.value, "column_name": "b"},
                {"uid": "y", "mismatch_type": MismatchType.MISSING_IN_TARGET.value, "column_name": None},
            ):
                fp.write(json.dumps(row) + "\n")
        assert _value_mismatch_row_count(mismatches=pl.DataFrame(), artifact=artifact) == 1
