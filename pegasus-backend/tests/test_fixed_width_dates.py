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


def test_validate_local_fixed_width_dob_slice_cross_formats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sample script layout: DOB at 58:68, DD/MM/YYYY vs YYYY/MM/DD should match."""
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "scripts" / "source_data.txt"
    tgt = repo_root / "scripts" / "target_data.txt"
    if not src.is_file() or not tgt.is_file():
        pytest.skip("scripts/source_data.txt and scripts/target_data.txt not present")

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src.resolve()),
                "target_path": str(tgt.resolve()),
                "delimiter": "fixed",
                "fixed_width_config": {
                    "source_date_start": 58,
                    "source_date_end": 68,
                    "source_date_format": "dd/mm/yyyy",
                    "target_date_start": 58,
                    "target_date_end": 68,
                    "target_date_format": "yyyy/mm/dd",
                },
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["is_match"] is True
        assert body["mismatch_counts"]["value_mismatch"] == 0


def test_validate_local_fixed_width_routes_via_delimiter_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Jobs with delimiter=fixed and draft column_mappings must not fall back to CSV."""
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    line = "00001   Alice Smith         alice@example.com             10/06/2026\n"
    src = tmp_path / "source.txt"
    tgt = tmp_path / "target.txt"
    src.write_text(line, encoding="utf-8")
    tgt.write_text(line.replace("10/06/2026", "2026/06/10"), encoding="utf-8")

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "delimiter": "fixed-width",
                "column_mappings": [
                    {"source_column": "source_date_start", "target_column": "58"},
                    {"source_column": "source_date_end", "target_column": "68"},
                    {"source_column": "source_date_format", "target_column": "dd/mm/yyyy"},
                    {"source_column": "target_date_start", "target_column": "58"},
                    {"source_column": "target_date_end", "target_column": "68"},
                    {"source_column": "target_date_format", "target_column": "yyyy/mm/dd"},
                ],
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["is_match"] is True
