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
