"""Tests for composite (1-to-many) name column mapping and reconstruction."""

from __future__ import annotations

from pathlib import Path
import pytest
import polars as pl

from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService
from pegasus.schemas.validation import ColumnMapping

@pytest.fixture
def service() -> ValidationService:
    get_settings.cache_clear()
    return ValidationService(settings=get_settings())

def test_composite_name_mapping_first_last(tmp_path: Path, service: ValidationService) -> None:
    source_content = "id,Full Name\n1,John Smith\n2,Jane Doe\n"
    target_content = "id,first_name,last_name\n1,John,Smith\n2,Jane,Doe\n"
    
    source_path = tmp_path / "source.csv"
    target_path = tmp_path / "target.csv"
    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")
    
    column_mappings = [
        ColumnMapping(source_column="Full Name", target_column="first_name"),
        ColumnMapping(source_column="Full Name", target_column="last_name")
    ]
    
    result = service._validate_csv_pair_sync(
        source_path=source_path,
        target_path=target_path,
        uid_column="id",
        delimiter=",",
        column_mappings=column_mappings
    )
    
    assert result.report.summary.get("value_mismatch", 0) == 0
    assert "Full Name" in result.compared_columns


def test_composite_name_mapping_first_middle_last(tmp_path: Path, service: ValidationService) -> None:
    source_content = "id,Full Name\n1,John F Kennedy\n2,Jane Doe\n"
    target_content = "id,first,middle,last\n1,John,F,Kennedy\n2,Jane,,Doe\n"
    
    source_path = tmp_path / "source.csv"
    target_path = tmp_path / "target.csv"
    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")
    
    column_mappings = [
        ColumnMapping(source_column="Full Name", target_column="first"),
        ColumnMapping(source_column="Full Name", target_column="middle"),
        ColumnMapping(source_column="Full Name", target_column="last")
    ]
    
    result = service._validate_csv_pair_sync(
        source_path=source_path,
        target_path=target_path,
        uid_column="id",
        delimiter=",",
        column_mappings=column_mappings
    )
    
    assert result.report.summary.get("value_mismatch", 0) == 0
    assert "Full Name" in result.compared_columns


def test_composite_name_mapping_with_mismatch(tmp_path: Path, service: ValidationService) -> None:
    source_content = "id,Full Name\n1,John Smith\n"
    # Target has a typo in last name
    target_content = "id,first_name,last_name\n1,John,Smyth\n"
    
    source_path = tmp_path / "source.csv"
    target_path = tmp_path / "target.csv"
    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")
    
    column_mappings = [
        ColumnMapping(source_column="Full Name", target_column="first_name"),
        ColumnMapping(source_column="Full Name", target_column="last_name")
    ]
    
    result = service._validate_csv_pair_sync(
        source_path=source_path,
        target_path=target_path,
        uid_column="id",
        delimiter=",",
        column_mappings=column_mappings
    )
    
    assert result.report.summary.get("value_mismatch", 0) == 1


def test_composite_name_mapping_target_columns_list(tmp_path: Path, service: ValidationService) -> None:
    source_content = "id,Full Name\n1,John Smith\n2,Jane Doe\n"
    target_content = "id,first_name,last_name\n1,John,Smith\n2,Jane,Doe\n"
    
    source_path = tmp_path / "source.csv"
    target_path = tmp_path / "target.csv"
    source_path.write_text(source_content, encoding="utf-8")
    target_path.write_text(target_content, encoding="utf-8")
    
    # Using the new target_columns list field inside ColumnMapping
    column_mappings = [
        ColumnMapping(
            source_column="Full Name",
            target_column="first_name",
            target_columns=["first_name", "last_name"]
        )
    ]
    
    result = service._validate_csv_pair_sync(
        source_path=source_path,
        target_path=target_path,
        uid_column="id",
        delimiter=",",
        column_mappings=column_mappings
    )
    
    assert result.report.summary.get("value_mismatch", 0) == 0
    assert "Full Name" in result.compared_columns
