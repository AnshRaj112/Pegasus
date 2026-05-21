"""Tests for fixed-width date parsing and cross-format comparison."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.services.validation_job_queue import reset_validation_queue
from pegasus.services.validation_service import ValidationService
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
                    "uid_column": "id",
                    "uid_source_start": 0,
                    "uid_source_end": 5,
                    "uid_target_start": 0,
                    "uid_target_end": 5,
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


def test_validate_fixed_width_inferred_layout_reads_full_field_width(
    tmp_path: Path,
) -> None:
    """Preview-inferred slices must include padding to the next column (not token end)."""
    from pegasus.core.config import get_settings

    def _line(uid: str, name: str, email: str, dob: str) -> str:
        return f"{uid:<5}   {name:<20}{email:<30}{dob:<10}\n"

    src = tmp_path / "source.txt"
    tgt = tmp_path / "target.txt"
    rows = [
        _line("00000", "User_0", "user0@example.com", "16/11/1964"),
        _line("0000a", "User_10", "user10@example.com", "01/02/2003"),
    ]
    src.write_text("".join(rows), encoding="utf-8")
    tgt.write_text("".join(reversed(rows)), encoding="utf-8")

    svc = ValidationService(get_settings())
    layout = svc.preview_fixed_width_layout(source_path=src, target_path=tgt)
    config = {
        "uid_column": "id",
        "fields": layout["columns"],
        "match_strategy": "exact",
    }
    for col in config["fields"]:
        if col["field_name"] == "dob":
            col["field_type"] = "date"
            col["source_date_format"] = "dd/mm/yyyy"
            col["target_date_format"] = "dd/mm/yyyy"

    result = svc.validate_fixed_width_pair_sync(src, tgt, config)
    assert result.report.summary["value_mismatch"] == 0


def test_validate_local_fixed_width_complete_aligns_by_uid_when_shuffled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Complete fixed-width mode should join by UID slices instead of line order."""
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()

    def _line(uid: str, name: str, email: str, dob: str) -> str:
        return f"{uid:<5}   {name:<20}{email:<30}{dob:<10}\n"

    src = tmp_path / "source.txt"
    tgt = tmp_path / "target.txt"
    src.write_text(
        "".join(
            [
                _line("00000", "User_0", "user0@example.com", "16/11/1964"),
                _line("00001", "User_1", "user1@example.com", "27/06/1960"),
                _line("00002", "User_2", "user2@example.com", "16/11/1999"),
            ]
        ),
        encoding="utf-8",
    )
    tgt.write_text(
        "".join(
            [
                _line("00002", "User_2", "user2@example.com", "1999/11/16"),
                _line("00000", "User_0", "user0@example.com", "1964/11/16"),
                _line("00001", "User_1-ERR", "user1@example.com", "1960/06/27"),
            ]
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "file_format": "fixed-width",
                "fixed_width_config": {
                    "uid_column": "id",
                    "uid_source_start": 0,
                    "uid_source_end": 5,
                    "uid_target_start": 0,
                    "uid_target_end": 5,
                    "fields": [
                        {
                            "field_name": "name",
                            "field_type": "text",
                            "source_start": 8,
                            "source_end": 28,
                            "target_start": 8,
                            "target_end": 28,
                        },
                        {
                            "field_name": "email",
                            "field_type": "text",
                            "source_start": 28,
                            "source_end": 58,
                            "target_start": 28,
                            "target_end": 58,
                        },
                        {
                            "field_name": "dob",
                            "field_type": "date",
                            "source_start": 58,
                            "source_end": 68,
                            "target_start": 58,
                            "target_end": 68,
                            "source_date_format": "dd/mm/yyyy",
                            "target_date_format": "yyyy/mm/dd",
                        },
                    ],
                },
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["source_row_count"] == 3
        assert body["summary"]["target_row_count"] == 3
        assert body["mismatch_counts"]["value_mismatch"] == 1


def test_validate_local_fixed_width_date_only_reports_all_line_mismatches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Date-only mode must scan every line and report non-date slice differences."""
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        src = tmp_path / "source.txt"
        tgt = tmp_path / "target.txt"
        # Date slice 5:13 (YYYYMMDD). Line 1: same date, different name suffix.
        # Line 2: different calendar date in the slice.
        src.write_text(
            "ID00120260101NAMEAAAA\n"
            "ID00220260102NAMEAAAA\n",
            encoding="utf-8",
        )
        tgt.write_text(
            "ID00120260101NAMEBBBB\n"
            "ID00220260202NAMEAAAA\n",
            encoding="utf-8",
        )
        r = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "file_format": "fixed-width",
                "fixed_width_config": {
                    "uid_column": "id",
                    "uid_source_start": 0,
                    "uid_source_end": 5,
                    "uid_target_start": 0,
                    "uid_target_end": 5,
                    "source_date_start": 5,
                    "source_date_end": 13,
                    "source_date_format": "%Y%m%d",
                    "target_date_start": 5,
                    "target_date_end": 13,
                    "target_date_format": "%Y%m%d",
                },
            },
        )
        assert r.status_code == 202, r.text
        body = _poll_completed(client, r.json()["poll_url"])
        assert body["summary"]["source_row_count"] == 2
        assert body["mismatch_counts"]["value_mismatch"] >= 1
        samples = body.get("mismatch_sample_groups") or {}
        columns = {row["column_name"] for row in samples.get("value_mismatch", [])}
        assert columns & {"date", "dob"}
        for row in samples.get("value_mismatch", []):
            assert row["column_name"] != "line"
