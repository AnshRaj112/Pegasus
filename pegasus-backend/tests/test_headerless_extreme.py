# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-28T11:56:30Z
# --- END GENERATED FILE METADATA ---

"""Headerless CSV handling and partition reconcile imports."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from pegasus.core.config import get_settings
from pegasus.schemas.validation import ColumnMapping
from pegasus.services.validation_service import ValidationService
from pegasus.validation.csv_header import infer_csv_has_header, infer_has_header_from_fields
from pegasus.validation.pipeline.partition_reconcile import load_partition_frame, partition_has_arrow

ROOT = Path(__file__).resolve().parents[2] / "test-data" / "extreme-testcase"
ROOT1 = ROOT / "source1.csv"
TGT1 = ROOT / "target1.csv"


def test_infer_record_id_rows_are_headerless() -> None:
    assert infer_has_header_from_fields(["ID001", "John Doe", "05/19/2026", "[1, 2, 3]"]) is False
    assert infer_has_header_from_fields(["R01", "Tech Dept", "01-Jan-2025", "[10, 20, 30]"]) is False
    assert infer_csv_has_header(ROOT / "source.csv", ",") is False


def test_partition_has_arrow_imported() -> None:
    assert callable(partition_has_arrow)
    assert load_partition_frame(Path("/tmp/nonexistent_part.bin")) is None


@pytest.mark.skipif(not (ROOT / "source.csv").is_file(), reason="fixtures missing")
def test_headerless_validation_runs() -> None:
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    preview = svc.preview_local_column_headers(
        source_path=ROOT / "source.csv",
        target_path=ROOT / "target.csv",
        uid_column="column_1",
        delimiter=",",
        has_header=False,
    )
    assert preview["source_columns"][0] == "column_1"
    assert preview["inferred_has_header"] is False
    assert "column_4" in preview["complex_columns"]
    assert preview["needs_order_preference"] is True

    result = svc._validate_csv_pair_sync(
        ROOT / "source.csv",
        ROOT / "target.csv",
        "column_1",
        ",",
        column_mappings=[
            ColumnMapping(source_column="column_2", target_column="column_2"),
            ColumnMapping(source_column="column_3", target_column="column_3"),
            ColumnMapping(source_column="column_4", target_column="column_4"),
        ],
        has_header=False,
    )
    assert result.source_row_count == 5
    assert result.target_row_count == 4
    assert result.report.summary["missing_in_target"] >= 1
    assert result.report.summary["extra_in_target"] >= 0
    if result.report.mismatches.height:
        assert result.report.mismatches["uid"][0] == "ID005"


@pytest.mark.skipif(not ROOT1.is_file() or not TGT1.is_file(), reason="fixtures missing")
def test_source1_target1_flexible_dates_and_structures() -> None:
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(
        ROOT1,
        TGT1,
        "column_1",
        ",",
        column_mappings=[
            ColumnMapping(source_column="column_2", target_column="column_2"),
            ColumnMapping(source_column="column_3", target_column="column_3"),
            ColumnMapping(
                source_column="column_4",
                target_column="column_4",
                compare_mode="structured",
                structured_order_sensitive=False,
            ),
        ],
        has_header=False,
    )
    summary = dict(result.report.summary)
    assert summary["missing_in_target"] == 1
    assert summary["extra_in_target"] == 1
    # R05 Finance/Financial, R07 ambiguous Jan-vs-Feb dates are real mismatches.
    assert summary["value_mismatch"] == 2
    mismatch_uids = set(result.report.mismatches.filter(
        pl.col("mismatch_type") == "value_mismatch"
    )["uid"].to_list()) if result.report.mismatches.height else set()
    assert mismatch_uids <= {"R05", "R07"}
