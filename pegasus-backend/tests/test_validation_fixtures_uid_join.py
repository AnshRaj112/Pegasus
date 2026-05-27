"""End-to-end UID join on shuffled test-data validation CSVs (no header row)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.services.validation_job_queue import reset_validation_queue


def _repo_test_data() -> Path:
    return Path(__file__).resolve().parents[2] / "test-data"


def _poll_completed(client: TestClient, poll_url: str, *, timeout_sec: float = 120.0) -> dict:
    import time

    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        gr = client.get(poll_url)
        assert gr.status_code == 200, gr.text
        payload = gr.json()
        if payload.get("status") == "completed":
            return payload["result"]
        if payload.get("status") == "failed":
            raise AssertionError(payload.get("error"))
        time.sleep(0.1)
    raise AssertionError("timeout")


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    reset_validation_queue()
    yield
    get_settings.cache_clear()
    reset_validation_queue()


def test_preview_validation_fixtures_positional_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _repo_test_data()
    source = root / "validation_source.csv"
    target = root / "validation_target.csv"
    if not source.is_file() or not target.is_file():
        pytest.skip("validation fixtures not present")

    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get(
            "/api/v1/validate/local/columns",
            params={
                "source_path": str(source),
                "target_path": str(target),
                "uid_column": "column_1",
                "delimiter": "auto",
                "has_header": "false",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delimiter"] == "xx"
    assert body["has_header"] is False
    assert body["inferred_has_header"] is False
    assert body["source_columns"] == ["column_1", "column_2", "column_3", "column_4"]
    assert body["source_samples"]["column_1"][:3] == ["1", "2", "3"]
    assert body["target_samples"]["column_1"][0] == "20014"


def test_validate_validation_fixtures_uid_join_not_row_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Target file is shuffled; counts prove join on column_1 (id), not row index."""
    root = _repo_test_data()
    source = root / "validation_source.csv"
    target = root / "validation_target.csv"
    if not source.is_file() or not target.is_file():
        pytest.skip("validation fixtures not present")

    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(source),
                "target_path": str(target),
                "uid_column": "column_1",
                "delimiter": "auto",
                "has_header": False,
                "column_mappings": [
                    {"source_column": "column_2", "target_column": "column_2"},
                    {"source_column": "column_3", "target_column": "column_3"},
                    {"source_column": "column_4", "target_column": "column_4"},
                ],
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])

    assert body["summary"]["source_row_count"] == 10_000
    assert body["summary"]["target_row_count"] == 10_000
    assert body["mismatch_counts"]["missing_in_target"] == 40
    assert body["mismatch_counts"]["extra_in_target"] == 40
    assert body["mismatch_counts"]["value_mismatch"] == 42
