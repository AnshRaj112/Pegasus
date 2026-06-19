# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T06:13:44Z
# --- END GENERATED FILE METADATA ---

"""Composite UID, regex transforms, and sensitive mismatch masking."""

from __future__ import annotations

from pathlib import Path

import pytest

from pegasus.core.config import get_settings
from pegasus.schemas.validation import ColumnMapping
from pegasus.services.validation_service import ValidationService
from pegasus.validation.comparators.core import apply_value_transform, resolve_regex_transform
from pegasus.validation.comparators.policy import ComparePolicy
from pegasus.validation.pipeline.fingerprint import parse_identity_columns


def test_parse_identity_columns() -> None:
    assert parse_identity_columns("region,id") == ["region", "id"]
    assert parse_identity_columns("id") == ["id"]
    assert parse_identity_columns("a,b,c,d,e") == ["a", "b", "c", "d", "e"]
    assert parse_identity_columns(" region , id , dept ") == ["region", "id", "dept"]


def test_regex_transform_plain_and_sql() -> None:
    assert resolve_regex_transform("[^0-9]", "") == ("[^0-9]", "")
    sql = "SELECT REGEXP_REPLACE(contact_number, '[^0-9]', '', 'g') AS clean_number"
    assert resolve_regex_transform(sql, "") == ("[^0-9]", "")
    assert apply_value_transform("+91-98765-43210", pattern="[^0-9]", replacement="") == "919876543210"


def test_policy_regex_normalizes_phone() -> None:
    policy = ComparePolicy.from_mappings(
        ["contact_number"],
        [
            ColumnMapping(
                source_column="contact_number",
                target_column="contact_number",
                source_regex_pattern="[^0-9]",
                source_regex_replacement="",
            )
        ],
        scanned_complex=set(),
    )
    src = {"contact_number": "+91-98765-43210"}
    tgt = {"contact_number": "919876543210"}
    assert policy.values_equal_mapped("contact_number", src, tgt)


def _write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


@pytest.fixture
def composite_uid_pair(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(
        src,
        "region,id,name",
        ["US,1,Alice", "US,2,Bob", "EU,3,Carol"],
    )
    _write_csv(
        tgt,
        "region,id,name",
        ["US,1,Alice", "US,2,Bobby", "EU,3,Carol"],
    )
    return src, tgt


def test_validation_composite_uid(composite_uid_pair: tuple[Path, Path]) -> None:
    src, tgt = composite_uid_pair
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(  # noqa: SLF001
        src,
        tgt,
        "region,id",
        ",",
        column_mappings=[ColumnMapping(source_column="name", target_column="name")],
        has_header=True,
    )
    summary = dict(result.report.summary)
    assert summary.get("value_mismatch", 0) == 1


def test_validation_five_column_composite_uid(tmp_path: Path) -> None:
    """Join on 5 UID columns; only the row with same composite key + different name mismatches."""
    uid_cols = ["region", "country", "dept", "team", "emp_id"]
    uid = ",".join(uid_cols)
    header = ",".join([*uid_cols, "name"])
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(
        src,
        header,
        [
            "APAC,IN,ENG,ALPHA,E001,Alice",
            "APAC,IN,ENG,ALPHA,E002,Bob",
            "EMEA,UK,HR,BETA,E003,Carol",
            "AMER,US,SALES,GAMMA,E004,Dave",
        ],
    )
    _write_csv(
        tgt,
        header,
        [
            "APAC,IN,ENG,ALPHA,E001,Alice",
            "APAC,IN,ENG,ALPHA,E002,Bobby",
            "EMEA,UK,HR,BETA,E003,Carol",
            "AMER,US,SALES,GAMMA,E004,Dave",
        ],
    )

    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(  # noqa: SLF001
        src,
        tgt,
        uid,
        ",",
        column_mappings=[ColumnMapping(source_column="name", target_column="name")],
        has_header=True,
    )
    summary = dict(result.report.summary)
    assert summary.get("missing_in_target", 0) == 0
    assert summary.get("extra_in_target", 0) == 0
    assert summary.get("value_mismatch", 0) == 1

    row = result.report.mismatches.filter(
        result.report.mismatches["mismatch_type"] == "value_mismatch"
    ).row(0, named=True)
    assert row["uid"] == "APAC|IN|ENG|ALPHA|E002"
    assert row["column_name"] == "name"


def test_validation_five_column_composite_uid_detects_missing_row(tmp_path: Path) -> None:
    """A row missing in target is detected when any of the 5 key parts differ."""
    uid = "region,country,dept,team,emp_id"
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(
        src,
        "region,country,dept,team,emp_id,name",
        ["APAC,IN,ENG,ALPHA,E001,Alice", "APAC,IN,ENG,ALPHA,E099,Zara"],
    )
    _write_csv(
        tgt,
        "region,country,dept,team,emp_id,name",
        ["APAC,IN,ENG,ALPHA,E001,Alice"],
    )

    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(  # noqa: SLF001
        src,
        tgt,
        uid,
        ",",
        column_mappings=[ColumnMapping(source_column="name", target_column="name")],
        has_header=True,
    )
    summary = dict(result.report.summary)
    assert summary.get("missing_in_target", 0) == 1
    assert summary.get("value_mismatch", 0) == 0


@pytest.fixture
def phone_pair(tmp_path: Path) -> tuple[Path, Path]:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(src, "id,contact_number", ["1,+91-98765-43210", "2,+1 (555) 010-9999"])
    _write_csv(tgt, "id,contact_number", ["1,919876543210", "2,15550109999"])
    return src, tgt


def test_validation_regex_phone(phone_pair: tuple[Path, Path]) -> None:
    src, tgt = phone_pair
    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(  # noqa: SLF001
        src,
        tgt,
        "id",
        ",",
        column_mappings=[
            ColumnMapping(
                source_column="contact_number",
                target_column="contact_number",
                source_regex_pattern="SELECT REGEXP_REPLACE(contact_number, '[^0-9]', '', 'g') AS clean_number",
                source_regex_replacement="",
            )
        ],
        has_header=True,
    )
    summary = dict(result.report.summary)
    assert summary.get("value_mismatch", 0) == 0


def test_validation_india_phone_source_and_target_expressions(tmp_path: Path) -> None:
    """Source +911234567890 should match target 1234567890 only with per-side expressions."""
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(src, "id,mobile", ["1,+911234567890"])
    _write_csv(tgt, "id,mobile", ["1,1234567890"])

    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(  # noqa: SLF001
        src,
        tgt,
        "id",
        ",",
        column_mappings=[
            ColumnMapping(
                source_column="mobile",
                target_column="mobile",
                source_regex_pattern=r"REGEXP_REPLACE(mobile, '^\+91', '', 'g')",
                target_regex_pattern=r"REGEXP_REPLACE(mobile, '[^0-9]', '', 'g')",
            )
        ],
        has_header=True,
    )
    assert dict(result.report.summary).get("value_mismatch", 0) == 0


def test_validation_india_phone_mismatches_without_expressions(tmp_path: Path) -> None:
    """Same values must mismatch when no source/target SQL expressions are configured."""
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(src, "id,mobile", ["1,+911234567890"])
    _write_csv(tgt, "id,mobile", ["1,1234567890"])

    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(  # noqa: SLF001
        src,
        tgt,
        "id",
        ",",
        column_mappings=[
            ColumnMapping(source_column="mobile", target_column="mobile"),
        ],
        has_header=True,
    )
    assert dict(result.report.summary).get("value_mismatch", 0) == 1


def test_policy_both_side_expressions_strip_plus91() -> None:
    policy = ComparePolicy.from_mappings(
        ["mobile"],
        [
            ColumnMapping(
                source_column="mobile",
                target_column="mobile",
                source_regex_pattern=r"^\+91",
                target_regex_pattern="[^0-9]",
            )
        ],
        scanned_complex=set(),
    )
    assert policy.values_equal_mapped(
        "mobile",
        {"mobile": "+911234567890"},
        {"mobile": "1234567890"},
    )


def test_policy_india_phone_mismatches_without_expressions() -> None:
    policy = ComparePolicy.from_mappings(
        ["mobile"],
        [ColumnMapping(source_column="mobile", target_column="mobile")],
        scanned_complex=set(),
    )
    assert not policy.values_equal_mapped(
        "mobile",
        {"mobile": "+911234567890"},
        {"mobile": "1234567890"},
    )


def test_sensitive_mismatch_masks_values(tmp_path: Path) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    _write_csv(src, "id,ssn", ["1,123-45-6789"])
    _write_csv(tgt, "id,ssn", ["1,999-99-9999"])

    get_settings.cache_clear()
    svc = ValidationService(get_settings())
    result = svc._validate_csv_pair_sync(  # noqa: SLF001
        src,
        tgt,
        "id",
        ",",
        column_mappings=[
            ColumnMapping(source_column="ssn", target_column="ssn", is_sensitive=True),
        ],
        has_header=True,
    )
    row = result.report.mismatches.row(0, named=True)
    assert row["source_value"] == "****"
    assert row["target_value"] == "****"
