# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-12T15:22:16+05:30
# --- END GENERATED FILE METADATA ---

"""Multi-column mapping: rename, 1:N, and N:1."""

from __future__ import annotations

from pathlib import Path

import pytest

from pegasus.core.config import get_settings
from pegasus.schemas.validation import ColumnMapping
from pegasus.services.validation_service import ValidationService
from pegasus.validation.comparators.mapping_resolver import (
    resolve_field_mappings,
    target_canonical_from_parts,
)
from pegasus.validation.comparators.policy import ComparePolicy


def test_resolve_field_mapping_rename() -> None:
    fm = resolve_field_mappings(
        [ColumnMapping(source_column="name", target_column="full_name")],
        scanned_complex=set(),
    )[0]
    assert fm.source_columns == ("name",)
    assert fm.target_columns == ("full_name",)


def test_resolve_field_mapping_one_to_many() -> None:
    fm = resolve_field_mappings(
        [
            ColumnMapping(
                source_column="phone",
                target_column="mobile",
                target_columns=["landline"],
            )
        ],
        scanned_complex=set(),
    )[0]
    assert fm.source_columns == ("phone",)
    assert fm.target_columns == ("mobile", "landline")


def test_resolve_field_mapping_many_to_one() -> None:
    fm = resolve_field_mappings(
        [
            ColumnMapping(
                source_column="full_name",
                source_columns=["first_name", "last_name"],
                target_column="name",
            )
        ],
        scanned_complex=set(),
    )[0]
    assert fm.source_columns == ("first_name", "last_name")
    assert fm.target_columns == ("name",)


def test_policy_values_equal_mapped() -> None:
    policy = ComparePolicy.from_mappings(
        ["full_name"],
        [
            ColumnMapping(
                source_column="full_name",
                source_columns=["first_name", "last_name"],
                target_column="name",
            )
        ],
        scanned_complex=set(),
    )
    src = {"first_name": "Jane", "last_name": "Doe"}
    tgt_match = {"name": "Jane Doe"}
    tgt_miss = {"name": "John Doe"}
    assert policy.values_equal_mapped("full_name", src, tgt_match)
    assert not policy.values_equal_mapped("full_name", src, tgt_miss)


def test_target_canonical_one_to_many_match() -> None:
    parts = ["555-0100", "555-0100"]
    assert target_canonical_from_parts(parts) == "555-0100"


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture
def rename_pair(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(src, "id,name", ["1,Alice", "2,Bob"])
    _write_csv(tgt, "id,full_name", ["1,Alice", "2,Bob"])
    return src, tgt


@pytest.fixture
def composite_pair(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(
        src,
        "id,first,last",
        ["1,Alice,Smith", "2,Bob,Jones"],
    )
    _write_csv(tgt, "id,full_name", ["1,Alice Smith", "2,Bob Jones"])
    return src, tgt


def test_validation_rename(rename_pair: tuple[Path, Path]) -> None:
    src, tgt = rename_pair
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(
        src,
        tgt,
        "id",
        ",",
        column_mappings=[ColumnMapping(source_column="name", target_column="full_name")],
        has_header=True,
    )
    summary = dict(result.report.summary)
    assert summary.get("value_mismatch", 0) == 0


def test_validation_many_to_one(composite_pair: tuple[Path, Path]) -> None:
    src, tgt = composite_pair
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(
        src,
        tgt,
        "id",
        ",",
        column_mappings=[
            ColumnMapping(
                source_column="full_name",
                source_columns=["first", "last"],
                target_column="full_name",
            )
        ],
        has_header=True,
    )
    summary = dict(result.report.summary)
    assert summary.get("value_mismatch", 0) == 0


def test_validation_one_to_many_phone(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(src, "id,phone", ["1,555-99", "2,555-00"])
    _write_csv(tgt, "id,mobile,landline", ["1,555-99,555-99", "2,555-00,555-01"])
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(
        src,
        tgt,
        "id",
        ",",
        column_mappings=[
            ColumnMapping(
                source_column="phone",
                target_column="mobile",
                target_columns=["landline"],
            )
        ],
        has_header=True,
    )
    summary = dict(result.report.summary)
    assert summary.get("value_mismatch", 0) == 1
