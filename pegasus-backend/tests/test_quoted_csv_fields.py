"""Quote-aware CSV parsing: commas inside addresses and similar fields."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.validation.flat_file import field_count, split_line
from pegasus.validation.readers.delimiter_detection import detect_delimiter


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
