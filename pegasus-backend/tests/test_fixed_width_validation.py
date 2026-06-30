# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T06:21:03Z
# --- END GENERATED FILE METADATA ---

"""Fixed-width validation, date formats, and DAT delimited fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pegasus.core.config import get_settings
from pegasus.schemas.validation import ColumnMapping, FixedWidthConfig, FixedWidthField
from pegasus.services.validation_service import ValidationService
from pegasus.validation.comparators.core import eq
from pegasus.validation.fixed_width import fields_equal, validate_fixed_width_pair
from pegasus.validation.fixed_width_dates import dates_equal_fixed_width, parse_fixed_width_date

REPO = Path(__file__).resolve().parents[2]
STRUCTURED = REPO / "test-data" / "structured-compare"
DAT = REPO / "test-data" / "dat-compare"


class TestFixedWidthDates:
    @pytest.mark.parametrize(
        "source,target",
        [
            ("19/05/2026", "05/19/2026"),
            ("31/12/2025", "12/31/2025"),
            ("15/08/2024", "08/15/2024"),
        ],
    )
    def test_cross_format_with_explicit_formats(self, source: str, target: str) -> None:
        assert dates_equal_fixed_width(
            source,
            target,
            source_date_format="DD/MM/YYYY",
            target_date_format="MM/DD/YYYY",
        )

    def test_parse_friendly_format(self) -> None:
        assert parse_fixed_width_date("19/05/2026", "DD/MM/YYYY").isoformat() == "2026-05-19"


class TestStructuredDictOrder:
    def test_dict_order_insensitive(self) -> None:
        field = FixedWidthField(
            field_name="payload",
            source_start=0,
            source_end=20,
            target_start=0,
            target_end=20,
            field_type="structured",
            structured_order_sensitive=False,
        )
        assert fields_equal('{"x": 1, "y": 2}', '{"y": 2, "x": 1}', field)

    def test_dict_order_sensitive(self) -> None:
        field = FixedWidthField(
            field_name="payload",
            source_start=0,
            source_end=20,
            target_start=0,
            target_end=20,
            field_type="structured",
            structured_order_sensitive=True,
        )
        assert not fields_equal('{"x": 1, "y": 2}', '{"y": 2, "x": 1}', field)

    def test_comparator_json_literals(self) -> None:
        assert eq('{"a": 1, "b": 2}', '{"b": 2, "a": 1}', complex_mode=True, order=False)
        assert not eq('{"a": 1, "b": 2}', '{"b": 2, "a": 1}', complex_mode=True, order=True)


@pytest.mark.skipif(not STRUCTURED.joinpath("manifest.json").is_file(), reason="fixtures missing")
def test_structured_fixed_width_fixture() -> None:
    manifest = json.loads((STRUCTURED / "manifest.json").read_text(encoding="utf-8"))
    report = validate_fixed_width_pair(
        STRUCTURED / "fixed-width" / "source.dat",
        STRUCTURED / "fixed-width" / "target.dat",
        manifest["fixed_width_config"],
    )
    summary = dict(report.summary)
    assert summary["missing_in_target"] == 1
    assert summary["extra_in_target"] == 1
    assert summary["value_mismatch"] == 2


@pytest.mark.skipif(not STRUCTURED.joinpath("csv/source.csv").is_file(), reason="fixtures missing")
def test_structured_csv_dict_order_modes() -> None:
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    loose = svc._validate_csv_pair_sync(
        STRUCTURED / "csv" / "source.csv",
        STRUCTURED / "csv" / "target.csv",
        uid_column="id",
        delimiter=",",
        column_mappings=[
            ColumnMapping(source_column="tags", target_column="tags"),
            ColumnMapping(source_column="metadata", target_column="metadata"),
        ],
        has_header=True,
    )
    strict = svc._validate_csv_pair_sync(
        STRUCTURED / "csv" / "source.csv",
        STRUCTURED / "csv" / "target.csv",
        uid_column="id",
        delimiter=",",
        column_mappings=[
            ColumnMapping(
                source_column="tags",
                target_column="tags",
                compare_mode="structured",
                structured_order_sensitive=True,
            ),
            ColumnMapping(
                source_column="metadata",
                target_column="metadata",
                compare_mode="structured",
                structured_order_sensitive=True,
            ),
        ],
        has_header=True,
    )
    assert loose.report.summary["value_mismatch"] < strict.report.summary["value_mismatch"]


@pytest.mark.skipif(not DAT.joinpath("many-to-one/target.dat").is_file(), reason="fixtures missing")
def test_dat_files_validate_as_delimited() -> None:
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(
        DAT / "many-to-one" / "source_part1.dat",
        DAT / "many-to-one" / "target.dat",
        uid_column="id",
        delimiter=",",
        column_mappings=[ColumnMapping(source_column="name", target_column="name")],
        has_header=True,
    )
    assert result.report.summary["extra_in_target"] == 1
    assert result.report.summary["value_mismatch"] == 0
