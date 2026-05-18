"""Tests for trailing-row footer parsing."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.footer_validation import read_trailing_csv_rows


def test_read_trailing_rows_multichar_delimiter(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id||x\n1||a\nTOTAL||99\n", encoding="utf-8")
    rows = read_trailing_csv_rows(path, delimiter="||", trailing_rows=1)
    assert rows == [["TOTAL", "99"]]


def test_read_trailing_rows_single_char_delimiter(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id,x\n1,a\nTOTAL,99\n", encoding="utf-8")
    rows = read_trailing_csv_rows(path, delimiter=",", trailing_rows=1)
    assert rows == [["TOTAL", "99"]]
