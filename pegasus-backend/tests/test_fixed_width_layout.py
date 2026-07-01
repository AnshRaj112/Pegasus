# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T14:53:09Z
# --- END GENERATED FILE METADATA ---

"""Tests for fixed-width layout inference."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.fixed_width_layout import (
    build_column_previews,
    infer_date_format_friendly,
    infer_field_boundaries,
    read_sample_lines_from_path,
)

FIXTURE = Path(__file__).resolve().parents[2] / "test-data" / "structured-compare" / "fixed-width"


def test_infer_field_boundaries_finds_metadata_gutter() -> None:
    lines = read_sample_lines_from_path(FIXTURE / "source.dat")
    segments = infer_field_boundaries(lines)
    assert any(start == 60 for start, _end in segments)


def test_build_column_previews_assigns_widths() -> None:
    src = read_sample_lines_from_path(FIXTURE / "source.dat")
    tgt = read_sample_lines_from_path(FIXTURE / "target.dat")
    columns = build_column_previews(src, tgt)
    assert columns
    assert all(col.width == max(col.source_end - col.source_start, col.target_end - col.target_start) for col in columns)
    assert columns[0].field_name == "record_id"


def test_build_column_previews_generated_10k_four_columns() -> None:
    root = Path(__file__).resolve().parents[2] / "test-data" / "generated-10k-fixed_width"
    src = read_sample_lines_from_path(root / "source_data.txt")
    tgt = read_sample_lines_from_path(root / "target_data.txt")
    columns = build_column_previews(src, tgt)
    assert len(columns) == 4
    assert columns[0].field_name == "record_id"
    assert columns[1].field_name == "name"
    assert columns[2].field_name == "email"
    assert columns[3].field_name == "date"
    assert columns[0].source_sample == "00000"
    assert columns[0].target_sample == "0019O"
    assert columns[3].source_date_format == "DD/MM/YYYY"
    assert columns[3].target_date_format == "YYYY/MM/DD"


def test_infer_date_format_friendly() -> None:
    assert infer_date_format_friendly(["31/12/2024", "01/01/2025"]) == "DD/MM/YYYY"
    assert infer_date_format_friendly(["12/31/2024"]) == "MM/DD/YYYY"
