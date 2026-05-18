"""Unit tests for column format inference."""

from __future__ import annotations

from pegasus.validation.format_profiles import FormatKind, check_mapping_format, infer_format


def test_infer_email() -> None:
    profile = infer_format(["a@b.com", "x@y.org", "bad"])
    assert profile.kind == FormatKind.EMAIL
    assert profile.confidence >= 0.6


def test_infer_iso_date() -> None:
    profile = infer_format(["2024-01-01", "2024-12-31"])
    assert profile.kind == FormatKind.ISO_DATE


def test_mapping_date_mismatch() -> None:
    result = check_mapping_format(
        source_column="d1",
        target_column="d2",
        source_values=["2024-01-01"],
        target_values=["01/01/2024"],
    )
    assert result["compatible"] is False
    assert "date" in (result["message"] or "").lower()


def test_mapping_same_format() -> None:
    result = check_mapping_format(
        source_column="e1",
        target_column="e2",
        source_values=["a@b.com"],
        target_values=["c@d.com"],
    )
    assert result["compatible"] is True
