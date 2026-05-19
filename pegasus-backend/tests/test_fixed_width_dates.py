"""Tests for fixed-width date parsing and cross-format comparison."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.services.validation_job_queue import reset_validation_queue
from pegasus.validation.fixed_width_dates import normalize_strptime_format, parse_fixed_width_date


@pytest.fixture(autouse=True)
def _clear_settings_cache_each_test() -> None:
    get_settings.cache_clear()
    reset_validation_queue()
    yield
    get_settings.cache_clear()
    reset_validation_queue()


@pytest.mark.parametrize(
    ("friendly", "expected"),
    [
        ("dd-mm-yyyy", "%d-%m-%Y"),
        ("mm/dd/yyyy", "%m/%d/%Y"),
        ("yyyy-mm-dd", "%Y-%m-%d"),
        ("%Y-%m-%d", "%Y-%m-%d"),
    ],
)
def test_normalize_strptime_format(friendly: str, expected: str) -> None:
    assert normalize_strptime_format(friendly) == expected


def test_parse_fixed_width_date_cross_notation() -> None:
    assert parse_fixed_width_date("19-05-2026", "dd-mm-yyyy") == date(2026, 5, 19)
    assert parse_fixed_width_date("05-19-2026", "mm-dd-yyyy") == date(2026, 5, 19)
    assert parse_fixed_width_date("2026-05-19", "yyyy-mm-dd") == date(2026, 5, 19)


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


def test_validate_local_fixed_width_different_date_formats(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Same calendar date in different string formats should validate as a match."""
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "source.txt"
        tgt = tmp_path / "target.txt"
        src.write_text("REC0119-05-2026\nREC0221-05-2026\n", encoding="utf-8")
        tgt.write_text("REC0105-19-2026\nREC0205-19-2026\n", encoding="utf-8")

        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "file_format": "fixed-width",
                "fixed_width_config": {
                    "source_date_start": 5,
                    "source_date_end": 15,
                    "source_date_format": "dd-mm-yyyy",
                    "target_date_start": 5,
                    "target_date_end": 15,
                    "target_date_format": "mm-dd-yyyy",
                },
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["source_row_count"] == 2
        assert body["summary"]["target_row_count"] == 2
        assert body["mismatch_counts"]["value_mismatch"] == 1
        assert body["mismatch_counts"]["missing_in_target"] == 0
        assert body["mismatch_counts"]["extra_in_target"] == 0
