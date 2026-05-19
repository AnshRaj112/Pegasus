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


