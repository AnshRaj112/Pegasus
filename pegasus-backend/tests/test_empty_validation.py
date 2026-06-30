# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T10:37:33Z
# --- END GENERATED FILE METADATA ---

"""Empty source/target/both validation scenarios."""

from __future__ import annotations

from pathlib import Path

import pytest

from pegasus.core.config import get_settings
from pegasus.schemas.validation import ColumnMapping, FixedWidthConfig, FixedWidthField
from pegasus.services.validation_service import ValidationService
from pegasus.validation.empty_inputs import file_has_no_content
from pegasus.validation.fixed_width import validate_fixed_width_pair


@pytest.fixture
def svc() -> ValidationService:
    get_settings.cache_clear()
    return ValidationService(get_settings())


def _fw_config() -> FixedWidthConfig:
    return FixedWidthConfig(
        uid_column="record_id",
        fields=[
            FixedWidthField(
                field_name="record_id",
                source_start=0,
                source_end=4,
                target_start=0,
                target_end=4,
                field_type="text",
            ),
            FixedWidthField(
                field_name="name",
                source_start=4,
                source_end=20,
                target_start=4,
                target_end=20,
                field_type="text",
            ),
        ],
    )


class TestEmptyFileDetection:
    def test_zero_bytes(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        path.write_bytes(b"")
        assert file_has_no_content(path)

    def test_whitespace_only(self, tmp_path: Path) -> None:
        path = tmp_path / "blank.csv"
        path.write_text("\n\n  \n", encoding="utf-8")
        assert file_has_no_content(path)

    def test_header_only_is_not_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "header.csv"
        path.write_text("id,name\n", encoding="utf-8")
        assert not file_has_no_content(path)


class TestDelimitedEmptyCases:
    def test_source_empty_target_has_rows(self, tmp_path: Path, svc: ValidationService) -> None:
        src = tmp_path / "source.csv"
        tgt = tmp_path / "target.csv"
        src.write_bytes(b"")
        tgt.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")

        result = svc._validate_csv_pair_sync(
            src,
            tgt,
            uid_column="id",
            delimiter=",",
            column_mappings=[ColumnMapping(source_column="name", target_column="name")],
            has_header=True,
        )
        summary = dict(result.report.summary)
        assert result.source_row_count == 0
        assert result.target_row_count == 2
        assert summary["missing_in_target"] == 0
        assert summary["extra_in_target"] == 2
        assert summary["value_mismatch"] == 0

    def test_target_empty_source_has_rows(self, tmp_path: Path, svc: ValidationService) -> None:
        src = tmp_path / "source.csv"
        tgt = tmp_path / "target.csv"
        src.write_text("id,name\n1,alice\n", encoding="utf-8")
        tgt.write_bytes(b"")

        result = svc._validate_csv_pair_sync(
            src,
            tgt,
            uid_column="id",
            delimiter=",",
            column_mappings=[ColumnMapping(source_column="name", target_column="name")],
            has_header=True,
        )
        summary = dict(result.report.summary)
        assert result.source_row_count == 1
        assert result.target_row_count == 0
        assert summary["missing_in_target"] == 1
        assert summary["extra_in_target"] == 0
        assert summary["value_mismatch"] == 0

    def test_both_empty(self, tmp_path: Path, svc: ValidationService) -> None:
        src = tmp_path / "source.csv"
        tgt = tmp_path / "target.csv"
        src.write_bytes(b"")
        tgt.write_text("\n\n", encoding="utf-8")

        result = svc._validate_csv_pair_sync(
            src,
            tgt,
            uid_column="id",
            delimiter=",",
            column_mappings=[ColumnMapping(source_column="name", target_column="name")],
            has_header=True,
        )
        summary = dict(result.report.summary)
        assert result.source_row_count == 0
        assert result.target_row_count == 0
        assert summary == {
            "missing_in_target": 0,
            "extra_in_target": 0,
            "value_mismatch": 0,
            "value_mismatch_rows": 0,
        }

    def test_dat_extension_empty_source(self, tmp_path: Path, svc: ValidationService) -> None:
        src = tmp_path / "source.dat"
        tgt = tmp_path / "target.dat"
        src.write_bytes(b"")
        tgt.write_text("id,name\n10,neo\n", encoding="utf-8")

        result = svc._validate_csv_pair_sync(
            src,
            tgt,
            uid_column="id",
            delimiter=",",
            column_mappings=[ColumnMapping(source_column="name", target_column="name")],
            has_header=True,
        )
        assert result.report.summary["extra_in_target"] == 1


class TestFixedWidthEmptyCases:
    def test_source_empty_target_has_rows(self, tmp_path: Path, svc: ValidationService) -> None:
        src = tmp_path / "source.dat"
        tgt = tmp_path / "target.dat"
        src.write_bytes(b"")
        tgt.write_text("1   alice             \n", encoding="utf-8")

        result = svc.validate_fixed_width_pair_sync(src, tgt, _fw_config())
        assert result.source_row_count == 0
        assert result.target_row_count == 1
        assert result.report.summary["extra_in_target"] == 1

    def test_target_empty_source_has_rows(self, tmp_path: Path, svc: ValidationService) -> None:
        src = tmp_path / "source.dat"
        tgt = tmp_path / "target.dat"
        src.write_text("1   alice             \n", encoding="utf-8")
        tgt.write_bytes(b"")

        result = svc.validate_fixed_width_pair_sync(src, tgt, _fw_config())
        assert result.source_row_count == 1
        assert result.target_row_count == 0
        assert result.report.summary["missing_in_target"] == 1

    def test_both_empty(self, tmp_path: Path) -> None:
        src = tmp_path / "source.dat"
        tgt = tmp_path / "target.dat"
        src.write_bytes(b"")
        tgt.write_text("   \n", encoding="utf-8")

        report = validate_fixed_width_pair(src, tgt, _fw_config())
        assert report.summary == {
            "missing_in_target": 0,
            "extra_in_target": 0,
            "value_mismatch": 0,
            "value_mismatch_rows": 0,
        }
