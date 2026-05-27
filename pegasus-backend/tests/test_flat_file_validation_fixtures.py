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
# Files have no header row; parse_file uses column_0 … when has_header=False.
_EXPECTED_HEADERS = ["column_0", "column_1", "column_2", "column_3"]
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
        ColumnSchema("column_0", type=ColumnType.INTEGER, min_length=1, max_length=6),
        ColumnSchema("column_1", pattern=r"SKU-\d{5}"),
        ColumnSchema("column_2", type=ColumnType.INTEGER),
        ColumnSchema("column_3", pattern=r"^(EMEA|APAC|AMER)$"),
    ]


def test_validation_source_parses_with_xx_delimiter(validation_source_path: Path) -> None:
    result = parse_file(validation_source_path, _VALIDATION_DELIMITER, has_header=False)
    assert result.ok
    assert result.headers == _EXPECTED_HEADERS
    assert result.expected_column_count == 4
    assert len(result.rows) == _EXPECTED_DATA_ROWS
    assert result.column_count_errors == []


def test_validation_target_parses_with_xx_delimiter(validation_target_path: Path) -> None:
    result = parse_file(validation_target_path, _VALIDATION_DELIMITER, has_header=False)
    assert result.ok
    assert result.headers == _EXPECTED_HEADERS
    assert len(result.rows) == _EXPECTED_DATA_ROWS
    assert result.column_count_errors == []


def test_validation_source_row_order_and_sample_values(validation_source_path: Path) -> None:
    result = parse_file(validation_source_path, _VALIDATION_DELIMITER, has_header=False)
    assert result.rows[0] == ["1", "SKU-00001", "101", "EMEA"]
    assert result.rows[1] == ["2", "SKU-00002", "102", "APAC"]
    last = result.rows[-1]
    assert last[:3] == ["10000", "SKU-10000", "100"]
    assert last[3].strip() == "EMEA"


def test_validation_target_is_shuffled_vs_source(
    validation_source_path: Path,
    validation_target_path: Path,
) -> None:
    source = parse_file(validation_source_path, _VALIDATION_DELIMITER, has_header=False)
    target = parse_file(validation_target_path, _VALIDATION_DELIMITER, has_header=False)
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
        has_header=False,
        strip_fields=True,
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
        has_header=False,
    )
    region_errors = [e for e in result.schema_errors if e.column == "column_3"]
    assert len(region_errors) == 12
    assert all(e.value == "LATAM" for e in region_errors)
    assert not result.ok


def test_validation_source_all_regions_valid(validation_source_path: Path) -> None:
    result = parse_file(
        validation_source_path,
        _VALIDATION_DELIMITER,
        has_header=False,
        strip_fields=True,
    )
    regions = {row[3] for row in result.rows}
    assert regions == _REGIONS


def test_validation_files_share_most_ids_but_differ_by_40(
    validation_source_path: Path,
    validation_target_path: Path,
) -> None:
    """Fixtures are built for Pegasus validation: 40 id rows differ between sides."""
    source = parse_file(validation_source_path, _VALIDATION_DELIMITER, has_header=False)
    target = parse_file(validation_target_path, _VALIDATION_DELIMITER, has_header=False)
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
    source = parse_file(validation_source_path, _VALIDATION_DELIMITER, has_header=False)
    target = parse_file(validation_target_path, _VALIDATION_DELIMITER, has_header=False)
    src_map = {row[0]: row for row in source.rows}
    tgt_map = {row[0]: row for row in target.rows}
    common = set(src_map) & set(tgt_map)
    mismatches = [uid for uid in common if src_map[uid] != tgt_map[uid]]
    assert len(mismatches) == 38


def test_validation_target_includes_latam_region_rows(validation_target_path: Path) -> None:
    result = parse_file(validation_target_path, _VALIDATION_DELIMITER, has_header=False)
    latam = [row for row in result.rows if row[3] == "LATAM"]
    assert len(latam) == 12


def test_validation_source_id_amount_invariant(validation_source_path: Path) -> None:
    """amount = 100 + (id % 50) for the sequential source fixture."""
    result = parse_file(validation_source_path, _VALIDATION_DELIMITER, has_header=False)
    for row in result.rows[::1000]:
        row_id = int(row[0])
        expected_amount = str(100 + (row_id % 50))
        assert row[2] == expected_amount, f"id={row_id}"
