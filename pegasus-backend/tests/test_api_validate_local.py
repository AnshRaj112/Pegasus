"""Tests for POST /api/v1/validate/local."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
        assert body["source_columns"] == ["name", "city"]
        assert body["target_columns"] == ["city", "full_name"]
        assert body["auto_mappings"] == [{"source_column": "city", "target_column": "city"}]
        assert body["unmatched_source_columns"] == ["name"]


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


def test_browse_local_parent_navigation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    nested = tmp_path / "nested"
    nested.mkdir()
    with TestClient(create_app()) as client:
        r = client.get("/api/v1/validate/local/browse", params={"path": str(nested)})
        assert r.status_code == 200, r.text
        assert r.json()["parent_path"] == str(tmp_path.resolve())
