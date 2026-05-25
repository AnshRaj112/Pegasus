"""Integration tests: flat_file parser on repo test-data validation CSVs.

Files use the multi-character delimiter ``xx`` (not comma). Field names and
values must not contain the substring ``xx`` except as a separator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pegasus.validation.flat_file import (
    ColumnSchema,
    ColumnType,
    parse_and_validate,
    parse_file,
)

_VALIDATION_DELIMITER = "xx"
_EXPECTED_HEADERS = ["id", "sku", "amount", "region"]
_EXPECTED_DATA_ROWS = 10_000
_REGIONS = frozenset({"EMEA", "APAC", "AMER"})


def _test_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "test-data"


@pytest.fixture(scope="module")
def validation_source_path() -> Path:
    path = _test_data_dir() / "validation_source.csv"
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path


@pytest.fixture(scope="module")
def validation_target_path() -> Path:
    path = _test_data_dir() / "validation_target.csv"
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path


@pytest.fixture(scope="module")
def validation_schema() -> list[ColumnSchema]:
    return [
        ColumnSchema("id", type=ColumnType.INTEGER, min_length=1, max_length=6),
        ColumnSchema("sku", pattern=r"SKU-\d{5}"),
        ColumnSchema("amount", type=ColumnType.INTEGER),
        ColumnSchema("region", pattern=r"^(EMEA|APAC|AMER)$"),
    ]


def test_validation_source_parses_with_xx_delimiter(validation_source_path: Path) -> None:
    result = parse_file(validation_source_path, _VALIDATION_DELIMITER)
    assert result.ok
    assert result.headers == _EXPECTED_HEADERS
    assert result.expected_column_count == 4
    assert len(result.rows) == _EXPECTED_DATA_ROWS
    assert result.column_count_errors == []


def test_validation_target_parses_with_xx_delimiter(validation_target_path: Path) -> None:
    result = parse_file(validation_target_path, _VALIDATION_DELIMITER)
    assert result.ok
    assert result.headers == _EXPECTED_HEADERS
    assert len(result.rows) == _EXPECTED_DATA_ROWS
    assert result.column_count_errors == []


def test_validation_source_row_order_and_sample_values(validation_source_path: Path) -> None:
    result = parse_file(validation_source_path, _VALIDATION_DELIMITER)
    assert result.rows[0] == ["1", "SKU-00001", "101", "EMEA"]
    assert result.rows[1] == ["2", "SKU-00002", "102", "APAC"]
    assert result.rows[-1] == ["10000", "SKU-10000", "100", "EMEA"]


def test_validation_target_is_shuffled_vs_source(
    validation_source_path: Path,
    validation_target_path: Path,
) -> None:
    source = parse_file(validation_source_path, _VALIDATION_DELIMITER)
    target = parse_file(validation_target_path, _VALIDATION_DELIMITER)
    assert source.rows[0][0] == "1"
    assert target.rows[0][0] == "20014"
    assert source.rows[0] != target.rows[0]
    assert [r[0] for r in source.rows[:5]] == ["1", "2", "3", "4", "5"]
    assert [r[0] for r in target.rows[:5]] == ["20014", "8327", "6647", "4967", "3287"]


def test_validation_source_schema_passes(
    validation_source_path: Path,
    validation_schema: list[ColumnSchema],
) -> None:
    result = parse_and_validate(
        validation_source_path,
        _VALIDATION_DELIMITER,
        validation_schema,
    )
    assert result.schema_errors == []
    assert result.ok


def test_validation_target_schema_reports_region_mismatches(
    validation_target_path: Path,
    validation_schema: list[ColumnSchema],
) -> None:
    """Target fixture includes rows with region LATAM (invalid for source schema)."""
    result = parse_and_validate(
        validation_target_path,
        _VALIDATION_DELIMITER,
        validation_schema,
    )
    region_errors = [e for e in result.schema_errors if e.column == "region"]
    assert len(region_errors) == 12
    assert all(e.value == "LATAM" for e in region_errors)
    assert not result.ok


def test_validation_source_all_regions_valid(validation_source_path: Path) -> None:
    result = parse_file(validation_source_path, _VALIDATION_DELIMITER)
    regions = {row[3] for row in result.rows}
    assert regions == _REGIONS


def test_validation_files_share_most_ids_but_differ_by_40(
    validation_source_path: Path,
    validation_target_path: Path,
) -> None:
    """Fixtures are built for Pegasus validation: 40 id rows differ between sides."""
    source = parse_file(validation_source_path, _VALIDATION_DELIMITER)
    target = parse_file(validation_target_path, _VALIDATION_DELIMITER)
    src_ids = {row[0] for row in source.rows}
    tgt_ids = {row[0] for row in target.rows}
    assert len(src_ids) == _EXPECTED_DATA_ROWS
    assert len(tgt_ids) == _EXPECTED_DATA_ROWS
    assert len(src_ids & tgt_ids) == 9960
    assert len(src_ids - tgt_ids) == 40
    assert len(tgt_ids - src_ids) == 40
    assert "1000" in src_ids and "1000" not in tgt_ids
    assert "20001" in tgt_ids and "20001" not in src_ids
    assert "1" in src_ids and "1" in tgt_ids


def test_validation_common_ids_include_value_mismatches(
    validation_source_path: Path,
    validation_target_path: Path,
) -> None:
    source = parse_file(validation_source_path, _VALIDATION_DELIMITER)
    target = parse_file(validation_target_path, _VALIDATION_DELIMITER)
    src_map = {row[0]: row for row in source.rows}
    tgt_map = {row[0]: row for row in target.rows}
    common = set(src_map) & set(tgt_map)
    mismatches = [uid for uid in common if src_map[uid] != tgt_map[uid]]
    assert len(mismatches) == 38


def test_validation_target_includes_latam_region_rows(validation_target_path: Path) -> None:
    result = parse_file(validation_target_path, _VALIDATION_DELIMITER)
    latam = [row for row in result.rows if row[3] == "LATAM"]
    assert len(latam) == 12


def test_validation_source_id_amount_invariant(validation_source_path: Path) -> None:
    """amount = 100 + (id % 50) for the sequential source fixture."""
    result = parse_file(validation_source_path, _VALIDATION_DELIMITER)
    for row in result.rows[::1000]:
        row_id = int(row[0])
        expected_amount = str(100 + (row_id % 50))
        assert row[2] == expected_amount, f"id={row_id}"
