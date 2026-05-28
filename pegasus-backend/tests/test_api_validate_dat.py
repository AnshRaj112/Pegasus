"""DAT-format API coverage for local, pairing, and batch flows."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.services.validation_job_queue import reset_validation_queue


@pytest.fixture(autouse=True)
def _clear_settings_cache_each_test() -> None:
    get_settings.cache_clear()
    reset_validation_queue()
    yield
    get_settings.cache_clear()
    reset_validation_queue()


def _poll_completed(client: TestClient, poll_url: str, *, timeout_sec: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        resp = client.get(poll_url)
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        if payload.get("status") == "completed":
            return payload
        if payload.get("status") == "failed":
            raise AssertionError(payload.get("error"))
        time.sleep(0.05)
    raise AssertionError("timeout while waiting for validation job")


def test_match_pairs_includes_dat_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    src_dir = tmp_path / "src"
    tgt_dir = tmp_path / "tgt"
    src_dir.mkdir()
    tgt_dir.mkdir()

    (src_dir / "alpha.dat").write_text("id,name\n1,alice\n", encoding="utf-8")
    (src_dir / "ignore.csv").write_text("id,name\n1,alice\n", encoding="utf-8")
    (tgt_dir / "alpha.dat").write_text("id,name\n1,alice\n", encoding="utf-8")
    (tgt_dir / "beta.dat").write_text("id,name\n2,bob\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        resp = client.post(
            "/api/v1/validate/local/match-pairs",
            json={
                "source_directory": str(src_dir),
                "target_directory": str(tgt_dir),
                "file_format": "dat",
                "recursive": False,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["pairs"]) == 1
        assert body["pairs"][0]["source_name"] == "alpha.dat"
        assert body["pairs"][0]["target_name"] == "alpha.dat"
        assert body["unmatched_targets"] == [str((tgt_dir / "beta.dat").resolve())]


def test_validate_local_dat_happy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    src = tmp_path / "source.dat"
    tgt = tmp_path / "target.dat"
    src.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    tgt.write_text("id,name\n1,alice\n2,robert\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        queued = client.post(
            "/api/v1/validate/local",
            json={
                "source_path": str(src),
                "target_path": str(tgt),
                "file_format": "dat",
                "uid_column": "id",
                "delimiter": ",",
                "test_mode": "full",
            },
        )
        assert queued.status_code == 202, queued.text
        completed = _poll_completed(client, queued.json()["poll_url"])
        result = completed["result"]
        assert result["summary"]["source_row_count"] == 2
        assert result["mismatch_counts"]["value_mismatch"] == 1


def test_validate_local_batch_dat_merge_layouts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    src_single = tmp_path / "src_single.dat"
    tgt_part_a = tmp_path / "tgt_part_a.dat"
    tgt_part_b = tmp_path / "tgt_part_b.dat"
    src_part_a = tmp_path / "src_part_a.dat"
    src_part_b = tmp_path / "src_part_b.dat"
    tgt_single = tmp_path / "tgt_single.dat"

    src_single.write_text("id,name\n1,alice\n2,bob\n3,cara\n", encoding="utf-8")
    tgt_part_a.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    tgt_part_b.write_text("id,name\n3,cora\n", encoding="utf-8")

    src_part_a.write_text("id,name\n10,neo\n", encoding="utf-8")
    src_part_b.write_text("id,name\n11,trin\n", encoding="utf-8")
    tgt_single.write_text("id,name\n10,neo\n11,trinity\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        queued = client.post(
            "/api/v1/validate/local/batch",
            json={
                "file_format": "dat",
                "delimiter": ",",
                "has_header": True,
                "on_unit_failure": "continue",
                "test_mode": "full",
                "units": [
                    {
                        "unit_id": "source-one-target-many",
                        "source_paths": [str(src_single)],
                        "target_paths": [str(tgt_part_a), str(tgt_part_b)],
                        "uid_column": "id",
                        "column_mappings": [{"source_column": "name", "target_column": "name"}],
                    },
                    {
                        "unit_id": "source-many-target-one",
                        "source_paths": [str(src_part_a), str(src_part_b)],
                        "target_paths": [str(tgt_single)],
                        "uid_column": "id",
                        "column_mappings": [{"source_column": "name", "target_column": "name"}],
                    },
                ],
            },
        )
        assert queued.status_code == 202, queued.text
        completed = _poll_completed(client, queued.json()["poll_url"])
        batch = completed["batch_result"]
        assert batch["summary"]["total_units"] == 2
        unit_status = {u["unit_id"]: u for u in batch["units"]}
        assert unit_status["source-one-target-many"]["status"] == "completed"
        assert unit_status["source-many-target-one"]["status"] == "completed"
        assert unit_status["source-one-target-many"]["result"]["mismatch_counts"]["value_mismatch"] == 1
        assert unit_status["source-many-target-one"]["result"]["mismatch_counts"]["value_mismatch"] == 1
