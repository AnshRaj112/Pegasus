"""Edge-case CSV validation aligned with docs/csv-validation-test-cases.md."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.services.validation_job_queue import reset_validation_queue
from pegasus.validation.csv_preflight import CsvPreflightError, preflight_csv_structure
from pegasus.validation.readers import PolarsCSVReader


def _poll_completed(client: TestClient, poll_url: str, *, timeout_sec: float = 30.0) -> dict:
    import time

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        gr = client.get(poll_url)
        assert gr.status_code == 200, gr.text
        if not gr.content:
            time.sleep(0.05)
            continue
        try:
            payload = gr.json()
        except Exception:
            time.sleep(0.05)
            continue
        if payload.get("status") == "completed":
            return payload["result"]
        if payload.get("status") == "failed":
            raise AssertionError(payload.get("error"))
        time.sleep(0.05)
    raise AssertionError("timeout")


def _poll_failed(client: TestClient, poll_url: str, *, timeout_sec: float = 30.0) -> str:
    import time

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        gr = client.get(poll_url)
        assert gr.status_code == 200, gr.text
        if not gr.content:
            time.sleep(0.05)
            continue
        try:
            payload = gr.json()
        except Exception:
            time.sleep(0.05)
            continue
        if payload.get("status") == "failed":
            return str(payload.get("error") or "")
        if payload.get("status") == "completed":
            raise AssertionError("expected failed job")
        time.sleep(0.05)
    raise AssertionError("timeout")


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    reset_validation_queue()
    yield
    get_settings.cache_clear()
    reset_validation_queue()


# --- preflight unit tests ---


def test_preflight_rejects_zero_byte_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")
    with pytest.raises(CsvPreflightError, match="empty input"):
        preflight_csv_structure(path, ",")


def test_preflight_rejects_gzip_disguised_as_csv(tmp_path: Path) -> None:
    path = tmp_path / "fake.csv"
    path.write_bytes(b"\x1f\x8b\x08\x00" + b"rest")
    with pytest.raises(CsvPreflightError, match="gzip"):
        preflight_csv_structure(path, ",")


def test_preflight_rejects_utf16_bom(tmp_path: Path) -> None:
    path = tmp_path / "utf16.csv"
    path.write_bytes(b"\xff\xfe" + "id,name\n1,a\n".encode("utf-16-le"))
    with pytest.raises(CsvPreflightError, match="UTF-16"):
        preflight_csv_structure(path, ",")


def test_preflight_accepts_utf8_bom_header(tmp_path: Path) -> None:
    path = tmp_path / "bom.csv"
    path.write_text("\ufeffid,name\n1,alice\n", encoding="utf-8")
    preflight_csv_structure(path, ",")
    reader = PolarsCSVReader()
    df = reader.read_file(path, delimiter=",")
    assert "id" in df.columns


def test_preflight_multiline_quoted_field(tmp_path: Path) -> None:
    path = tmp_path / "multi.csv"
    path.write_text('id,bio\n1,"Line1\nLine2"\n', encoding="utf-8")
    preflight_csv_structure(path, ",")
    df = PolarsCSVReader().read_file(path, delimiter=",")
    assert df.height == 1
    assert "Line1\nLine2" in df["bio"][0]


def test_preflight_trailing_comma_extra_field(tmp_path: Path) -> None:
    path = tmp_path / "trail.csv"
    path.write_text("a,b\n1,2,\n", encoding="utf-8")
    with pytest.raises(CsvPreflightError, match="row 2 has 3 field"):
        preflight_csv_structure(path, ",")


def test_preflight_short_row(tmp_path: Path) -> None:
    path = tmp_path / "short.csv"
    path.write_text("a,b,c\n1,2\n", encoding="utf-8")
    with pytest.raises(CsvPreflightError, match="row 2 has 2 field"):
        preflight_csv_structure(path, ",")


def test_preflight_quoted_commas_in_address(tmp_path: Path) -> None:
    path = tmp_path / "addr.csv"
    path.write_text(
        "id,name,address\n"
        '1,"Vidit J. Tiwari","Pune, Maharashtra, 123456"\n',
        encoding="utf-8",
    )
    preflight_csv_structure(path, ",")


def test_preflight_escaped_double_quotes(tmp_path: Path) -> None:
    path = tmp_path / "quotes.csv"
    path.write_text(
        "id,message\n"
        '1,"He said ""Hello"" to the team"\n',
        encoding="utf-8",
    )
    preflight_csv_structure(path, ",")


def test_preflight_crlf_and_empty_fields(tmp_path: Path) -> None:
    path = tmp_path / "crlf.csv"
    path.write_bytes(b"a,b,c\r\n1,,3\r\n")
    preflight_csv_structure(path, ",")


def test_preflight_duplicate_headers(tmp_path: Path) -> None:
    path = tmp_path / "dup.csv"
    path.write_text("id,id\n1,2\n", encoding="utf-8")
    with pytest.raises(CsvPreflightError, match="duplicate header"):
        preflight_csv_structure(path, ",")


def test_preflight_empty_data_row(tmp_path: Path) -> None:
    path = tmp_path / "blank.csv"
    path.write_text("ID,Name\n1,Alice\n\n2,Bob\n", encoding="utf-8")
    with pytest.raises(CsvPreflightError, match="row 3 is empty"):
        preflight_csv_structure(path, ",")


def test_preflight_multichar_delimiter(tmp_path: Path) -> None:
    path = tmp_path / "pipes.csv"
    path.write_text("id||name\n1||alice\n", encoding="utf-8")
    preflight_csv_structure(path, "||")


def test_preflight_multichar_does_not_read_entire_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "pipes_big.csv"
    path.write_text("id||name\n1||alice\n", encoding="utf-8")

    def _raise_if_read_text(*_args, **_kwargs):
        raise AssertionError("preflight should not call Path.read_text for multichar delimiter")

    monkeypatch.setattr(Path, "read_text", _raise_if_read_text)
    preflight_csv_structure(path, "||")


def test_preflight_multichar_ignores_truncated_tail_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pegasus.validation import csv_preflight as mod

    path = tmp_path / "pipes_large.csv"
    payload = "id||name||amount\n" + "".join(f"{i}||sku-{i}||{i*10}\n" for i in range(1, 2000))
    path.write_text(payload, encoding="utf-8")

    monkeypatch.setattr(mod, "_MULTICHAR_PREFLIGHT_MAX_BYTES", 1024)
    preflight_csv_structure(path, "||")


# --- API: errors surface to validation job poll (frontend reads ``error``) ---


def test_validate_local_malformed_csv_surfaces_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text("a,b,c\n1,2\n", encoding="utf-8")
    tgt.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "a",
                "delimiter": ",",
            },
        )
        assert r.status_code == 202, r.text
        err = _poll_failed(client, r.json()["poll_url"])
        assert "row 2" in err.lower() or "field" in err.lower()


def test_validate_local_unclosed_quote_surfaces_polars_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    content = 'id,x\n1,"unclosed\n'
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text(content, encoding="utf-8")
    tgt.write_text("id,x\n1,ok\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
            },
        )
        assert r.status_code == 202, r.text
        err = _poll_failed(client, r.json()["poll_url"])
        assert "parse" in err.lower() or "csv" in err.lower() or "escaped" in err.lower()


def test_preview_columns_returns_400_for_malformed_csv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text("a,b,c\n1,2\n", encoding="utf-8")
    tgt.write_text("a,b,c\n1,2,3\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        r = client.get(
            "/api/v1/validate/local/columns",
            params={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "a",
                "delimiter": ",",
            },
        )
    assert r.status_code == 400, r.text
    assert "row 2" in r.json()["detail"].lower() or "field" in r.json()["detail"].lower()


def test_validate_local_valid_quoted_multiline_completes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    content = 'id,bio\n1,"Line1\nLine2"\n'
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text(content, encoding="utf-8")
    tgt.write_text(content, encoding="utf-8")

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["source_row_count"] == 1
