"""Quote-aware CSV parsing: commas inside addresses and similar fields."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.validation.flat_file import field_count, parse_lines, split_line
from pegasus.validation.readers.delimiter_detection import detect_delimiter


def _stdlib_fields(line: str, delimiter: str = ",") -> list[str]:
    return next(csv.reader([line], delimiter=delimiter, doublequote=True))


def test_field_count_ignores_commas_inside_quotes() -> None:
    line = '1,"Vidit J. Tiwari","Pune, Maharashtra, 123456"'
    assert field_count(line, ",") == 3
    assert field_count(line, ",") != line.count(",") + 1


def test_detect_delimiter_comma_with_quoted_addresses(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    path.write_text(
        "id,name,address\n"
        '1,"Vidit J. Tiwari","Pune, Maharashtra, 123456"\n'
        '2,"Jane Doe","Mumbai, MH, 400001"\n',
        encoding="utf-8",
    )
    assert detect_delimiter(path).delimiter == ","


def test_preview_columns_quoted_address_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    content = (
        "id,name,address\n"
        '1,"Vidit J. Tiwari","Pune, Maharashtra, 123456"\n'
    )
    src.write_text(content, encoding="utf-8")
    tgt.write_text(content, encoding="utf-8")

    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get(
            "/api/v1/validate/local/columns",
            params={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_columns"] == ["id", "name", "address"]
    assert body["compare_columns"] == ["name", "address"]


def test_footer_parsing_quoted_commas(tmp_path: Path) -> None:
    from pegasus.validation.footer_validation import read_trailing_csv_rows

    path = tmp_path / "data.csv"
    path.write_text(
        "id,note\n1,ok\n"
        'TOTAL,"Pune, Maharashtra, 123456"\n',
        encoding="utf-8",
    )
    rows = read_trailing_csv_rows(path, delimiter=",", trailing_rows=1)
    assert rows == [["TOTAL", "Pune, Maharashtra, 123456"]]


def test_multichar_delimiter_inside_quotes_not_split() -> None:
    line = '1xx"field with xx inside"xxok'
    assert split_line(line, "xx") == ["1", "field with xx inside", "ok"]


def test_escaped_double_quotes_inside_quoted_field() -> None:
    """Test case 3: literal double quotes encoded as ``\"\"`` inside a quoted field."""
    row = '1,"He said ""Hello"" to the team",ok'
    assert split_line(row, ",") == [
        "1",
        'He said "Hello" to the team',
        "ok",
    ]
    assert _stdlib_fields(row) == split_line(row, ",")
    result = parse_lines(
        ["id,note,status", row],
        ",",
    )
    assert result.rows[0][1] == 'He said "Hello" to the team'
    assert result.ok


@pytest.mark.parametrize(
    "line",
    [
        'a,"unclosed',
        'a,"field "" at end',
        'a,"field """ at end',
        '1,"foo,bar',
        'a,"x",b,"y',
        'a,b",c',
    ],
)
def test_unclosed_or_midfield_quotes_match_stdlib(line: str) -> None:
    """Test case 4: quotes that do not close before EOL or appear mid-field."""
    assert split_line(line, ",") == _stdlib_fields(line)


def test_validation_preview_escaped_quotes_in_csv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """End-to-end: column preview with escaped quotes in cell values."""
    content = (
        "id,message\n"
        '1,"Status: ""OK"""\n'
    )
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text(content, encoding="utf-8")
    tgt.write_text(content, encoding="utf-8")

    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get(
            "/api/v1/validate/local/columns",
            params={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_columns"] == ["id", "message"]
