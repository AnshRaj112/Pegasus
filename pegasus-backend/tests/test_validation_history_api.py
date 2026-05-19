"""Tests for GET /api/v1/validate/history."""

from __future__ import annotations

import uuid

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


def test_validation_history_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get("/api/v1/validate/history")
        assert r.status_code == 503
        assert "PEGASUS_ENABLE_VALIDATION_PERSISTENCE" in r.json()["detail"]


def test_validation_history_detail_unknown_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get(f"/api/v1/validate/history/{uuid.uuid4()}")
        assert r.status_code in {404, 503}


def test_delete_validation_history_run_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, patch
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    with patch("pegasus.api.v1.validation_history.ValidationRunRepository.delete_run", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = True
        with TestClient(create_app()) as client:
            run_id = uuid.uuid4()
            r = client.delete(f"/api/v1/validate/history/{run_id}")
            assert r.status_code == 204
            mock_delete.assert_awaited_once()


def test_delete_validation_history_run_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, patch
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    with patch("pegasus.api.v1.validation_history.ValidationRunRepository.delete_run", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = False
        with TestClient(create_app()) as client:
            run_id = uuid.uuid4()
            r = client.delete(f"/api/v1/validate/history/{run_id}")
            assert r.status_code == 404
            mock_delete.assert_awaited_once()


def test_delete_validation_history_by_pair_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, patch
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    with patch("pegasus.api.v1.validation_history.ValidationRunRepository.delete_runs_by_file_pair", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = 5  # deleted 5 runs
        with TestClient(create_app()) as client:
            r = client.delete("/api/v1/validate/history?source_path=src.csv&target_path=tgt.csv")
            assert r.status_code == 204
            mock_delete.assert_awaited_once()
            # Verify called with session, source_path, target_path
            args = mock_delete.call_args[0]
            assert args[1] == "src.csv"
            assert args[2] == "tgt.csv"


def test_delete_validation_history_by_pair_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, patch
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    with patch("pegasus.api.v1.validation_history.ValidationRunRepository.delete_runs_by_file_pair", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = 0
        with TestClient(create_app()) as client:
            r = client.delete("/api/v1/validate/history?source_path=src.csv&target_path=tgt.csv")
            assert r.status_code == 404


def test_delete_validation_history_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "false")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.delete(f"/api/v1/validate/history/{uuid.uuid4()}")
        assert r.status_code == 503
        
        r2 = client.delete("/api/v1/validate/history?source_path=src.csv&target_path=tgt.csv")
        assert r2.status_code == 503


def test_delete_validation_history_all_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, patch
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    with patch("pegasus.api.v1.validation_history.ValidationRunRepository.delete_all_runs", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = 10  # deleted 10 runs
        with TestClient(create_app()) as client:
            r = client.delete("/api/v1/validate/history?all=true")
            assert r.status_code == 204
            mock_delete.assert_awaited_once()


def test_delete_validation_history_missing_params(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.delete("/api/v1/validate/history")
        assert r.status_code == 400
        assert "Must provide either" in r.json()["detail"]


def test_save_validation_draft_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import AsyncMock, MagicMock, patch
    from pegasus.models import ValidationRun
    from pegasus.models.enums import ValidationRunStatus

    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()

    # Create a mock run
    mock_run = ValidationRun(
        id=uuid.uuid4(),
        status=ValidationRunStatus.PENDING,
        source_filename="src.csv",
        target_filename="tgt.csv",
        source_path="/absolute/src.csv",
        target_path="/absolute/tgt.csv",
        uid_column="id",
        delimiter=",",
        column_mappings=[{"source_column": "s", "target_column": "t"}],
        validate_header_formats=False,
        validate_footers=False,
    )

    # Patch AsyncSessionLocal
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    with patch("pegasus.api.v1.validation_history.AsyncSessionLocal", return_value=mock_session), \
         patch("pegasus.api.v1.validation_history._detail_from_run") as mock_detail:
        
        from datetime import datetime, UTC
        from pegasus.schemas.validation_history import ValidationHistoryDetail
        from pegasus.schemas.validation import MismatchCounts
        mock_detail.return_value = ValidationHistoryDetail(
            run_id=mock_run.id,
            status="pending",
            source_path=mock_run.source_path,
            target_path=mock_run.target_path,
            source_filename=mock_run.source_filename,
            target_filename=mock_run.target_filename,
            uid_column=mock_run.uid_column,
            delimiter=mock_run.delimiter,
            column_mappings=[],
            mapping_count=1,
            mismatch_counts=MismatchCounts(missing_in_target=0, extra_in_target=0, value_mismatch=0),
            created_at=datetime.now(UTC),
        )

        with TestClient(create_app()) as client:
            payload = {
                "source_path": "/absolute/src.csv",
                "target_path": "/absolute/tgt.csv",
                "uid_column": "id",
                "delimiter": ",",
                "column_mappings": [{"source_column": "s", "target_column": "t"}],
                "validate_header_formats": False,
                "validate_footers": False,
            }
            r = client.post("/api/v1/validate/history/draft", json=payload)
            assert r.status_code == 200
            assert r.json()["status"] == "pending"
            assert r.json()["source_filename"] == "src.csv"



