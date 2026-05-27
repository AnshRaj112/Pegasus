"""Tests for header-row inference on validation fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from pegasus.validation.csv_header import infer_csv_has_header, read_first_row_fields


def _repo_test_data() -> Path:
    return Path(__file__).resolve().parents[2] / "test-data"


@pytest.fixture(scope="module")
def validation_source_path() -> Path:
    path = _repo_test_data() / "validation_source.csv"
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path


@pytest.fixture(scope="module")
def validation_target_path() -> Path:
    path = _repo_test_data() / "validation_target.csv"
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path


def test_validation_fixtures_first_row_is_data_not_header(
    validation_source_path: Path,
    validation_target_path: Path,
) -> None:
    assert infer_csv_has_header(validation_source_path, "xx") is False
    assert infer_csv_has_header(validation_target_path, "xx") is False
    assert read_first_row_fields(validation_source_path, "xx") == ["1", "SKU-00001", "101", "EMEA"]
    assert read_first_row_fields(validation_target_path, "xx")[0] == "20014"


def test_infer_detects_real_header_row(tmp_path: Path) -> None:
    path = tmp_path / "with_header.csv"
    path.write_text("id,sku,amount,region\n1,SKU-00001,101,EMEA\n", encoding="utf-8")
    assert infer_csv_has_header(path, ",") is True
