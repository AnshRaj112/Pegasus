"""Tests for POST /api/v1/validate/local."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app


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
    return TestClient(create_app())


def test_validate_local_disabled_by_default(client: TestClient, tmp_path: Path) -> None:
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
    monkeypatch.setenv("PEGASUS_VALIDATION_LOCAL_PATH_ROOTS", str(tmp_path))
    get_settings.cache_clear()
    client = TestClient(create_app())
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
