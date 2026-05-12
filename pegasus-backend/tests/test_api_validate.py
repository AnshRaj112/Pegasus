"""Integration tests for POST /api/v1/validate (background jobs)."""

from __future__ import annotations

import io
import time

import pytest
from fastapi.testclient import TestClient

from pegasus.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def _poll_completed(client: TestClient, poll_url: str, *, timeout_sec: float = 30.0) -> dict:
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
        st = payload.get("status")
        if st == "completed":
            result = payload.get("result")
            assert result is not None
            return result
        if st == "failed":
            pytest.fail(f"job failed: {payload.get('error')}")
        time.sleep(0.05)
    pytest.fail("timeout waiting for validation job")


def test_validate_happy_path(client: TestClient) -> None:
    source = io.BytesIO(b"id,name\n1,alice\n2,bob\n")
    target = io.BytesIO(b"id,name\n1,alice\n2,robert\n")
    files = {
        "source_file": ("source.csv", source, "text/csv"),
        "target_file": ("target.csv", target, "text/csv"),
    }
    data = {"uid_column": "id", "delimiter": ","}
    r = client.post("/api/v1/validate", files=files, data=data)
    assert r.status_code == 202, r.text
    accepted = r.json()
    body = _poll_completed(client, accepted["poll_url"])
    assert body["summary"]["source_row_count"] == 2
    assert body["summary"]["target_row_count"] == 2
    assert body["summary"]["is_match"] is False
    assert body["mismatch_counts"]["value_mismatch"] >= 1
    assert len(body["mismatch_sample_groups"]["value_mismatch"]) >= 1
    assert "name" in body["compared_columns"]
    assert body.get("run_id") is None


def test_validate_missing_uid_column(client: TestClient) -> None:
    source = io.BytesIO(b"a,b\n1,2\n")
    target = io.BytesIO(b"a,b\n1,2\n")
    r = client.post(
        "/api/v1/validate",
        files={
            "source_file": ("s.csv", source, "text/csv"),
            "target_file": ("t.csv", target, "text/csv"),
        },
        data={"uid_column": "missing", "delimiter": ","},
    )
    assert r.status_code == 202, r.text
    poll = r.json()["poll_url"]
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        gr = client.get(poll)
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
            assert "not found" in str(payload.get("error", "")).lower()
            return
        if payload.get("status") == "completed":
            pytest.fail("expected job failure for missing uid column")
        time.sleep(0.05)
    pytest.fail("timeout waiting for failed job")


def test_validate_duplicate_uid_job_failed(client: TestClient) -> None:
    source = io.BytesIO(b"id,x\na,1\na,2\n")
    target = io.BytesIO(b"id,x\na,1\n")
    r = client.post(
        "/api/v1/validate",
        files={
            "source_file": ("s.csv", source, "text/csv"),
            "target_file": ("t.csv", target, "text/csv"),
        },
        data={"uid_column": "id", "delimiter": ","},
    )
    assert r.status_code == 202, r.text
    poll = r.json()["poll_url"]
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        gr = client.get(poll)
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
            err = str(payload.get("error", "")).lower()
            assert "duplicate" in err or "uid" in err
            return
        time.sleep(0.05)
    pytest.fail("timeout waiting for failed duplicate-uid job")


def test_validate_auto_detects_semicolon_delimiter(client: TestClient) -> None:
    source = io.BytesIO(b"id;name\n1;alice\n2;bob\n")
    target = io.BytesIO(b"id;name\n1;alice\n2;robert\n")
    r = client.post(
        "/api/v1/validate",
        files={
            "source_file": ("s.csv", source, "text/csv"),
            "target_file": ("t.csv", target, "text/csv"),
        },
        data={"uid_column": "id", "delimiter": "auto"},
    )
    assert r.status_code == 202, r.text
    body = _poll_completed(client, r.json()["poll_url"])
    assert body["mismatch_counts"]["value_mismatch"] == 1


def test_validate_auto_detects_tab_delimiter_without_user_input(client: TestClient) -> None:
    source = io.BytesIO(b"id\tname\n1\talice\n2\tbob\n")
    target = io.BytesIO(b"id\tname\n1\talice\n2\trobert\n")
    r = client.post(
        "/api/v1/validate",
        files={
            "source_file": ("s.tsv", source, "text/tab-separated-values"),
            "target_file": ("t.tsv", target, "text/tab-separated-values"),
        },
        data={"uid_column": "id"},
    )
    assert r.status_code == 202, r.text
    body = _poll_completed(client, r.json()["poll_url"])
    assert body["mismatch_counts"]["value_mismatch"] == 1


def test_validate_explicit_multichar_delimiter_uses_fallback_parser(client: TestClient) -> None:
    source = io.BytesIO(b"id||name\n1||alice\n2||bob\n")
    target = io.BytesIO(b"id||name\n1||alice\n2||robert\n")
    r = client.post(
        "/api/v1/validate",
        files={
            "source_file": ("s.csv", source, "text/csv"),
            "target_file": ("t.csv", target, "text/csv"),
        },
        data={"uid_column": "id", "delimiter": "||"},
    )
    assert r.status_code == 202, r.text
    body = _poll_completed(client, r.json()["poll_url"])
    assert body["mismatch_counts"]["value_mismatch"] == 1


def test_validate_auto_detects_multichar_delimiter(client: TestClient) -> None:
    source = io.BytesIO(b"id::name\n1::alice\n2::bob\n")
    target = io.BytesIO(b"id::name\n1::alice\n2::robert\n")
    r = client.post(
        "/api/v1/validate",
        files={
            "source_file": ("s.csv", source, "text/csv"),
            "target_file": ("t.csv", target, "text/csv"),
        },
        data={"uid_column": "id", "delimiter": "auto"},
    )
    assert r.status_code == 202, r.text
    body = _poll_completed(client, r.json()["poll_url"])
    assert body["mismatch_counts"]["value_mismatch"] == 1
