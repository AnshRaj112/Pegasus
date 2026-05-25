"""Integration tests for POST /api/v1/validate (background jobs)."""

from __future__ import annotations

import io
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.api.v1.validation import _run_result_from_job_dir
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


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


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
    from pegasus.core.config import get_settings
    if get_settings().enable_validation_persistence:
        assert body.get("run_id") is not None
    else:
        assert body.get("run_id") is None


def test_validate_poll_returns_mismatch_samples_when_not_streamed_to_disk(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-memory mismatch collector must still export NDJSON for the detailed report."""
    monkeypatch.setenv("PEGASUS_VALIDATION_STREAM_MISMATCHES_TO_DISK", "false")
    get_settings.cache_clear()

    lines_s = ["id,name", *[f"{i},src{i}" for i in range(1, 11)]]
    lines_t = [
        "id,name",
        *[f"{i},tgt{i}" if i in (2, 5, 8) else f"{i},src{i}" for i in range(1, 11)],
    ]
    source = io.BytesIO(("\n".join(lines_s) + "\n").encode())
    target = io.BytesIO(("\n".join(lines_t) + "\n").encode())
    r = client.post(
        "/api/v1/validate",
        files={
            "source_file": ("s.csv", source, "text/csv"),
            "target_file": ("t.csv", target, "text/csv"),
        },
        data={"uid_column": "id", "delimiter": ","},
    )
    assert r.status_code == 202, r.text
    body = _poll_completed(client, r.json()["poll_url"])
    assert body["mismatch_counts"]["value_mismatch"] == 3
    assert len(body["mismatch_sample_groups"]["value_mismatch"]) == 3


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


def test_run_result_resolves_absolute_artifact_path(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    run_id = uuid.uuid4()
    (job_dir / "meta.json").write_text('{"run_id": "%s"}' % run_id, encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    artifact = outside / "mismatches.ndjson"
    artifact.write_text('{"uid":"1"}\n', encoding="utf-8")

    (job_dir / "result.json").write_text(
        (
            '{'
            '"source_row_count": 2,'
            '"target_row_count": 2,'
            '"compared_column_count": 1,'
            '"compared_columns": ["name"],' 
            '"summary": {"missing_in_target": 1, "extra_in_target": 0, "value_mismatch": 0},'
            '"mismatch_artifact_path": "%s"'
            '}'
        )
        % str(artifact),
        encoding="utf-8",
    )

    vr, rid, _meta = _run_result_from_job_dir(job_dir)
    assert rid == run_id
    assert vr.mismatch_artifact_path == artifact
    assert vr.report.mismatch_artifact_path == artifact


def test_run_result_resolves_relative_artifact_path(tmp_path: Path) -> None:
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    run_id = uuid.uuid4()
    (job_dir / "meta.json").write_text('{"run_id": "%s"}' % run_id, encoding="utf-8")

    artifact = job_dir / "mismatches.ndjson"
    artifact.write_text('{"uid":"1"}\n', encoding="utf-8")
    (job_dir / "result.json").write_text(
        (
            '{'
            '"source_row_count": 2,'
            '"target_row_count": 2,'
            '"compared_column_count": 1,'
            '"compared_columns": ["name"],' 
            '"summary": {"missing_in_target": 1, "extra_in_target": 0, "value_mismatch": 0},'
            '"mismatch_artifact_rel": "mismatches.ndjson"'
            '}'
        ),
        encoding="utf-8",
    )

    vr, rid, _meta = _run_result_from_job_dir(job_dir)
    assert rid == run_id
    assert vr.mismatch_artifact_path == artifact
    assert vr.report.mismatch_artifact_path == artifact
