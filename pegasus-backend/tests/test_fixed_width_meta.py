"""Tests for fixed-width job/API config resolution."""

from __future__ import annotations

from pegasus.validation.fixed_width_meta import (
    coerce_local_validate_fields,
    fixed_width_config_from_column_mappings,
    is_fixed_width_run,
    resolve_fixed_width_config,
)


def test_is_fixed_width_run_from_delimiter_or_format() -> None:
    assert is_fixed_width_run(file_format="csv", delimiter="fixed")
    assert is_fixed_width_run(file_format="fixed-width", delimiter="auto")
    assert not is_fixed_width_run(file_format="csv", delimiter=",")


def test_rebuild_config_from_draft_column_mappings() -> None:
    mappings = [
        {"source_column": "source_date_start", "target_column": "58"},
        {"source_column": "source_date_end", "target_column": "68"},
        {"source_column": "source_date_format", "target_column": "dd/mm/yyyy"},
        {"source_column": "target_date_start", "target_column": "58"},
        {"source_column": "target_date_end", "target_column": "68"},
        {"source_column": "target_date_format", "target_column": "yyyy/mm/dd"},
    ]
    cfg = fixed_width_config_from_column_mappings(mappings)
    assert cfg is not None
    assert cfg["source_date_start"] == 58
    assert cfg["target_date_format"] == "yyyy/mm/dd"


def test_resolve_prefers_explicit_fixed_width_config() -> None:
    explicit = {"source_date_start": 5, "source_date_end": 15}
    cfg = resolve_fixed_width_config(
        file_format="fixed-width",
        delimiter="fixed",
        fixed_width_config=explicit,
        column_mappings=[],
    )
    assert cfg == explicit


def test_coerce_local_validate_fields() -> None:
    ff, delim, cfg = coerce_local_validate_fields(
        file_format="csv",
        delimiter="fixed-width",
        fixed_width_config=None,
        column_mappings=[
            {"source_column": "source_date_start", "target_column": "58"},
            {"source_column": "source_date_end", "target_column": "68"},
            {"source_column": "source_date_format", "target_column": "dd/mm/yyyy"},
            {"source_column": "target_date_start", "target_column": "58"},
            {"source_column": "target_date_end", "target_column": "68"},
            {"source_column": "target_date_format", "target_column": "yyyy/mm/dd"},
        ],
    )
    assert ff == "fixed-width"
    assert delim == "fixed"
    assert cfg is not None
    assert cfg["source_date_end"] == 68
