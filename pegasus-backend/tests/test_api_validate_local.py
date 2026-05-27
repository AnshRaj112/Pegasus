"""Tests for POST /api/v1/validate/local."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.api.v1 import validation as validation_api
from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.services.validation_job_queue import reset_validation_queue


@pytest.fixture(autouse=True)
def _clear_settings_cache_each_test() -> None:
    """Isolate env/monkeypatch changes from ``get_settings`` lru_cache across tests."""
    get_settings.cache_clear()
    reset_validation_queue()
    yield
    get_settings.cache_clear()
    reset_validation_queue()


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
            assert payload.get("result") is not None
            return payload["result"]
        if payload.get("status") == "failed":
            raise AssertionError(payload.get("error"))
        time.sleep(0.05)
    raise AssertionError("timeout")


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


def test_validate_local_disabled_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "false")
    monkeypatch.setenv("PEGASUS_VALIDATION_LOCAL_PATH_ROOTS", "")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("id,x\n1,a\n", encoding="utf-8")
        tgt.write_text("id,x\n1,a\n", encoding="utf-8")
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
            },
        )
        assert r.status_code == 403


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


def test_validate_local_empty_csv_pair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("id,name\n", encoding="utf-8")
        tgt.write_text("id,name\n", encoding="utf-8")
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
        assert "empty" in err.lower() and "data rows" in err.lower()


def test_validate_local_empty_csv_pair_multichar(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("id||name\n", encoding="utf-8")
        tgt.write_text("id||name\n", encoding="utf-8")
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": "||",
            },
        )
        assert r.status_code == 202, r.text
        err = _poll_failed(client, r.json()["poll_url"])
        assert "empty" in err.lower() and "data rows" in err.lower()


def test_validate_local_zero_byte_csv_pair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_bytes(b"")
        tgt.write_bytes(b"")
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
        assert "empty" in err.lower() and "data rows" in err.lower()


def test_validate_local_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
        tgt.write_text("id,name\n1,alice\n2,robert\n", encoding="utf-8")
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
        assert body["summary"]["source_row_count"] == 2
        assert body["mismatch_counts"]["value_mismatch"] >= 1
        assert body.get("value_mismatch_by_column_omitted") is False


def test_preview_local_columns_auto_matches_unsorted_headers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("id,name,city\n1,alice,paris\n", encoding="utf-8")
        tgt.write_text("city,id,full_name\nparis,1,alice\n", encoding="utf-8")
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
        assert body["source_columns"] == ["id", "name", "city"]
        assert body["target_columns"] == ["city", "id", "full_name"]
        assert body["compare_columns"] == ["name", "city"]
        assert body["auto_mappings"] == [{"source_column": "city", "target_column": "city"}]
        assert body["unmatched_source_columns"] == ["id", "name"]


def test_validate_local_with_explicit_column_mapping(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("id,name,city\n1,alice,paris\n2,bob,rome\n", encoding="utf-8")
        tgt.write_text("city,id,full_name\nparis,1,alice\nrome,2,bob\n", encoding="utf-8")
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
                "column_mappings": [{"source_column": "name", "target_column": "full_name"}],
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["is_match"] is True
        assert set(body["compared_columns"]) == {"city", "name"}


def test_validate_local_auto_detects_spaced_emoji_delimiter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    delim = "👍"
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text(
        f"id {delim} sku {delim} amount {delim} region {delim} attr4\n"
        f"1 {delim} SKU-0001 {delim} 100 {delim} EMEA {delim} one\n",
        encoding="utf-8",
    )
    tgt.write_text(
        f"id {delim} sku {delim} amount {delim} region {delim} attr4\n"
        f"1 {delim} SKU-0001 {delim} 101 {delim} EMEA {delim} one\n",
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": "auto",
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["source_row_count"] == 1
        assert body["summary"]["target_row_count"] == 1
        assert body["mismatch_counts"]["value_mismatch"] == 1


def test_validate_local_accepts_google_cloud_storage_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()

    def fake_download(cloud, dest_path: Path):
        if cloud.object_name == "source.csv":
            dest_path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
        else:
            dest_path.write_text("id,name\n1,alice\n2,robert\n", encoding="utf-8")
        return dest_path

    monkeypatch.setattr(validation_api, "_download_gcs_object_to_path", fake_download)

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_cloud": {
                    "provider": "google-cloud-storage",
                    "bucket": "demo-bucket",
                    "object_name": "source.csv",
                    "credentials_json": '{"type":"service_account","project_id":"demo"}',
                },
                "target_cloud": {
                    "provider": "google-cloud-storage",
                    "bucket": "demo-bucket",
                    "object_name": "target.csv",
                    "credentials_json": '{"type":"service_account","project_id":"demo"}',
                },
                "uid_column": "id",
                "delimiter": ",",
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["source_row_count"] == 2
        assert body["mismatch_counts"]["value_mismatch"] >= 1


def test_preview_local_columns_accepts_google_cloud_storage_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()

    def fake_download(cloud, dest_path: Path):
        if cloud.object_name == "source.csv":
            dest_path.write_text("id,name,city\n1,alice,paris\n", encoding="utf-8")
        else:
            dest_path.write_text("city,id,full_name\nparis,1,alice\n", encoding="utf-8")
        return dest_path

    monkeypatch.setattr(validation_api, "_download_gcs_object_to_path", fake_download)

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local/columns",
            json={
                "source_cloud": {
                    "provider": "google-cloud-storage",
                    "bucket": "demo-bucket",
                    "object_name": "source.csv",
                    "credentials_json": '{"type":"service_account","project_id":"demo"}',
                },
                "target_cloud": {
                    "provider": "google-cloud-storage",
                    "bucket": "demo-bucket",
                    "object_name": "target.csv",
                    "credentials_json": '{"type":"service_account","project_id":"demo"}',
                },
                "uid_column": "id",
                "delimiter": ",",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source_columns"] == ["id", "name", "city"]
        assert body["target_columns"] == ["city", "id", "full_name"]
        assert body["auto_mappings"] == [{"source_column": "city", "target_column": "city"}]


def test_browse_local_forbidden_when_local_paths_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "false")
    monkeypatch.setenv("PEGASUS_VALIDATION_LOCAL_PATH_ROOTS", "")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get("/api/v1/validate/local/browse", params={"path": str(tmp_path)})
        assert r.status_code == 403


def test_browse_local_defaults_to_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get("/api/v1/validate/local/browse")
        assert r.status_code == 200, r.text
        assert r.json()["path"] == "/"


def test_browse_local_lists_entries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        (tmp_path / "golden.csv").write_text("id\n1\n", encoding="utf-8")
        (tmp_path / "nested").mkdir()
        r = client.get("/api/v1/validate/local/browse", params={"path": str(tmp_path)})
        assert r.status_code == 200, r.text
        body = r.json()
        names = {e["name"] for e in body["entries"]}
        assert "golden.csv" in names
        assert "nested" in names
        assert body["truncated"] is False


def test_analyze_local_mapping_formats(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("id,created,email\n1,2024-01-01,a@b.com\n", encoding="utf-8")
        tgt.write_text("id,created,email\n1,01/01/2024,a@b.com\n", encoding="utf-8")
        r = client.post(
            "/api/v1/validate/local/analyze",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
                "column_mappings": [{"source_column": "created", "target_column": "created"}],
                "validate_header_formats": True,
                "validate_footers": False,
            },
        )
        assert r.status_code == 200, r.text
        checks = r.json()["format_checks"]
        assert len(checks) == 1
        assert checks[0]["source_format"] == "iso_date"
        assert checks[0]["target_format"] == "us_date"
        assert checks[0]["compatible"] is False


def test_validate_local_with_footer_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("id,x\n1,a\nTOTAL,1\n", encoding="utf-8")
        tgt.write_text("id,x\n1,a\nTOTAL,1\n", encoding="utf-8")
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
                "validate_footers": True,
                "footer_trailing_rows": 1,
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        footer = body.get("footer_validation")
        assert footer is not None
        assert footer["match"] is True


def test_browse_local_parent_navigation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    nested = tmp_path / "nested"
    nested.mkdir()
    with TestClient(create_app()) as client:
        r = client.get("/api/v1/validate/local/browse", params={"path": str(nested)})
        assert r.status_code == 200, r.text
        assert r.json()["parent_path"] == str(tmp_path.resolve())


def test_validate_local_fixed_width_complete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.txt"
        tgt = tmp_path / "t.txt"
        # Layout:
        # Col 0-5: ID (Join Key)
        # Col 5-13: Date (YYYYMMDD)
        # Col 13-17: Integer (Quantity)
        # Col 17-22: Text (Status)
        src.write_text(
            "USR01202401010042ACTIVE\n"
            "USR02202401020100PENDING\n",
            encoding="utf-8"
        )
        tgt.write_text(
            "USR01202401010042ACTIVE\n" # Match
            "USR02202401020099PAUSED \n", # Quantity Mismatch (100 vs 99), Status Mismatch (PENDING vs PAUSED)
            encoding="utf-8"
        )
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "file_format": "fixed-width",
                "fixed_width_config": {
                    "uid_column": "UserID",
                    "uid_source_start": 0,
                    "uid_source_end": 5,
                    "uid_target_start": 0,
                    "uid_target_end": 5,
                    "fields": [
                        {
                            "field_name": "TxDate",
                            "source_start": 5,
                            "source_end": 13,
                            "target_start": 5,
                            "target_end": 13,
                            "field_type": "date",
                            "date_format": "%Y%m%d"
                        },
                        {
                            "field_name": "Quantity",
                            "source_start": 13,
                            "source_end": 17,
                            "target_start": 13,
                            "target_end": 17,
                            "field_type": "integer"
                        },
                        {
                            "field_name": "Status",
                            "source_start": 17,
                            "source_end": 22,
                            "target_start": 17,
                            "target_end": 22,
                            "field_type": "text"
                        }
                    ]
                }
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["source_row_count"] == 2
        assert body["summary"]["target_row_count"] == 2
        assert body["summary"]["compared_column_count"] == 3
        assert set(body["compared_columns"]) == {"TxDate", "Quantity", "Status"}
        assert body["mismatch_counts"]["value_mismatch"] == 2


def test_preview_headerless_csv_uses_positional_columns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("101,alice,30\n102,bob,25\n103,cara,28\n", encoding="utf-8")
        tgt.write_text("101,alice,30\n102,bob,26\n103,cara,28\n", encoding="utf-8")
        r = client.get(
            "/api/v1/validate/local/columns",
            params={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "column_1",
                "delimiter": ",",
                "has_header": "false",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_header"] is False
        assert body["source_columns"] == ["column_1", "column_2", "column_3"]
        assert body["target_columns"] == ["column_1", "column_2", "column_3"]
        assert body["source_samples"]["column_1"][:3] == ["101", "102", "103"]
        assert body["source_samples"]["column_2"][:2] == ["alice", "bob"]
        assert body["target_samples"]["column_3"][-1] == "28"


def test_validate_headerless_csv_with_explicit_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "s.csv"
        tgt = tmp_path / "t.csv"
        src.write_text("101,alice\n102,bob\n", encoding="utf-8")
        tgt.write_text("101,alice\n102,robert\n", encoding="utf-8")
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "column_1",
                "delimiter": ",",
                "has_header": False,
                "column_mappings": [{"source_column": "column_2", "target_column": "column_2"}],
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["is_match"] is False
        assert body["mismatch_counts"]["value_mismatch"] == 1
