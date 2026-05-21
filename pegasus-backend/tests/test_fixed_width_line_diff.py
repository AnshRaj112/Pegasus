"""Tests for fixed-width non-date field diffing."""

from __future__ import annotations

from pegasus.validation.fixed_width_line_diff import diff_outer_field_mismatches


def test_diff_outer_field_mismatches_whitespace_columns() -> None:
    src = "001U4   User_7320         user7320@example.com"
    tgt = "0006b   User_383          user383@example.com"
    diffs = diff_outer_field_mismatches(src, tgt)
    assert diffs == [
        ("id", "001U4", "0006b"),
        ("name", "User_7320", "User_383"),
        ("email", "user7320@example.com", "user383@example.com"),
    ]


def test_diff_outer_field_mismatches_packed_span() -> None:
    diffs = diff_outer_field_mismatches("ID001NAMEAAAA", "ID001NAMEBBBB")
    assert diffs == [("content", "AAAA", "BBBB")]
