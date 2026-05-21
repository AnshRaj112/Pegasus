"""Tests for fixed-width column layout inference."""

from __future__ import annotations

from pegasus.validation.fixed_width_layout import infer_columns_from_line


def _line(uid: str, name: str, email: str, dob: str) -> str:
    return f"{uid:<5}   {name:<20}{email:<30}{dob:<10}"


def test_infer_columns_uses_field_width_not_token_end() -> None:
    """Padded fields must run to the next column start, not the last non-space character."""
    line = _line("0000a", "User_10", "user10@example.com", "01/02/2003")
    cols = {c["field_name"]: c for c in infer_columns_from_line(line)}

    assert cols["id"]["source_start"] == 0
    assert cols["id"]["source_end"] == 8
    assert cols["name"]["source_start"] == 8
    assert cols["name"]["source_end"] == 28
    assert cols["email"]["source_start"] == 28
    assert cols["email"]["source_end"] == 58
    assert cols["dob"]["source_start"] == 58
    assert cols["dob"]["source_end"] == len(line.rstrip("\n\r"))

    assert line[cols["name"]["source_start"] : cols["name"]["source_end"]].strip() == "User_10"
    assert line[cols["email"]["source_start"] : cols["email"]["source_end"]].strip() == "user10@example.com"


def test_infer_columns_short_first_line_does_not_shrink_later_fields() -> None:
    """First-line inference must not use token end when a longer value appears on another row."""
    short = _line("00000", "User_0", "user0@example.com", "16/11/1964")
    long = _line("0000a", "User_10", "user10@example.com", "01/02/2003")
    cols = {c["field_name"]: c for c in infer_columns_from_line(short)}

    assert long[cols["name"]["source_start"] : cols["name"]["source_end"]].strip() == "User_10"
    assert long[cols["email"]["source_start"] : cols["email"]["source_end"]].strip() == "user10@example.com"
