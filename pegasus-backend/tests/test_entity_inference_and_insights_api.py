# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T05:26:25Z
# --- END GENERATED FILE METADATA ---

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import ProgrammingError

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.models.enums import ValidationRunStatus
from pegasus.services.entity_inference_service import EntityDefinition, infer_entity_from_filenames


@pytest.fixture(autouse=True)
def _clear_settings_cache_each_test() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_infer_entity_from_employee_pattern() -> None:
    entities = [EntityDefinition(name="employee", display_name="Employee", aliases=["emp", "staff"])]
    inferred = infer_entity_from_filenames(
        "employee_220526_20260528121212.csv",
        "employee_220526_20260528121213.csv",
        entities,
    )
    assert inferred.inferred_entity == "employee"
    assert inferred.matched_existing is True


def test_entity_insights_api_groups_success_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()

    fake_runs = [
        SimpleNamespace(
            id=uuid4(),
            status=ValidationRunStatus.COMPLETED,
            source_filename="employee_220526_120001.csv",
            target_filename="employee_220526_120099.csv",
            completed_at=datetime.now(UTC),
            is_match=True,
            missing_in_target_count=0,
            extra_in_target_count=0,
            value_mismatch_count=0,
        ),
        SimpleNamespace(
            id=uuid4(),
            status=ValidationRunStatus.FAILED,
            source_filename="employee_220526_120002.csv",
            target_filename="employee_220526_120199.csv",
            completed_at=datetime.now(UTC),
            is_match=False,
            missing_in_target_count=1,
            extra_in_target_count=0,
            value_mismatch_count=3,
        ),
    ]

    with (
        patch("pegasus.api.v1.validation_history._list_entity_definitions", new_callable=AsyncMock) as mock_entities,
        patch("pegasus.api.v1.validation_history.ValidationRunRepository.list_recent", new_callable=AsyncMock) as mock_recent,
    ):
        mock_entities.return_value = [EntityDefinition(name="employee", display_name="Employee", aliases=["emp"])]
        mock_recent.return_value = fake_runs
        with TestClient(create_app()) as client:
            resp = client.get("/api/v1/validate/history/entities/insights?limit=25")
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["limit"] == 25
            assert len(payload["entities"]) == 1
            entity = payload["entities"][0]
            assert entity["inferred_entity"] == "employee"
            assert entity["success_count"] == 1
            assert entity["failed_count"] == 1


def test_entity_insights_fallback_when_entity_table_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    fake_runs = [
        SimpleNamespace(
            id=uuid4(),
            status=ValidationRunStatus.COMPLETED,
            source_filename="ledgerx_220526_120001.csv",
            target_filename="ledgerx_220526_120099.csv",
            completed_at=datetime.now(UTC),
            is_match=True,
            missing_in_target_count=0,
            extra_in_target_count=0,
            value_mismatch_count=0,
        )
    ]
    with (
        patch("pegasus.api.v1.validation_history._list_entity_definitions", new_callable=AsyncMock) as mock_entities,
        patch("pegasus.api.v1.validation_history.ValidationRunRepository.list_recent", new_callable=AsyncMock) as mock_recent,
    ):
        mock_entities.side_effect = ProgrammingError("select * from validation_entities", {}, Exception("undefined table"))
        mock_recent.return_value = fake_runs
        with TestClient(create_app()) as client:
            resp = client.get("/api/v1/validate/history/entities/insights?limit=10")
            assert resp.status_code == 200
            payload = resp.json()
            assert len(payload["entities"]) == 1
            assert payload["entities"][0]["inferred_entity"] == "ledgerx"


def test_entity_insights_fallback_with_generic_undefined_table_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    fake_runs = [
        SimpleNamespace(
            id=uuid4(),
            status=ValidationRunStatus.COMPLETED,
            source_filename="employee_220526_120001.csv",
            target_filename="employee_220526_120099.csv",
            completed_at=datetime.now(UTC),
            is_match=True,
            missing_in_target_count=0,
            extra_in_target_count=0,
            value_mismatch_count=0,
        )
    ]
    with (
        patch("pegasus.api.v1.validation_history._list_entity_definitions", new_callable=AsyncMock) as mock_entities,
        patch("pegasus.api.v1.validation_history.ValidationRunRepository.list_recent", new_callable=AsyncMock) as mock_recent,
    ):
        mock_entities.side_effect = Exception('relation "validation_entities" does not exist')
        mock_recent.return_value = fake_runs
        with TestClient(create_app()) as client:
            resp = client.get("/api/v1/validate/history/entities/insights?limit=10")
            assert resp.status_code == 200
            payload = resp.json()
            assert len(payload["entities"]) == 1


def test_entity_insights_rolls_back_after_missing_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_ENABLE_VALIDATION_PERSISTENCE", "true")
    get_settings.cache_clear()
    fake_runs = [
        SimpleNamespace(
            id=uuid4(),
            status=ValidationRunStatus.COMPLETED,
            source_filename="employee_220526_120001.csv",
            target_filename="employee_220526_120099.csv",
            completed_at=datetime.now(UTC),
            is_match=True,
            missing_in_target_count=0,
            extra_in_target_count=0,
            value_mismatch_count=0,
        )
    ]
    with (
        patch("pegasus.api.v1.validation_history._list_entity_definitions", new_callable=AsyncMock) as mock_entities,
        patch("pegasus.api.v1.validation_history.ValidationRunRepository.list_recent", new_callable=AsyncMock) as mock_recent,
        patch("pegasus.api.v1.validation_history.AsyncSessionLocal") as mock_session_local,
    ):
        session = AsyncMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = session
        mock_ctx.__aexit__.return_value = None
        mock_session_local.return_value = mock_ctx

        mock_entities.side_effect = Exception('relation "validation_entities" does not exist')
        mock_recent.return_value = fake_runs

        with TestClient(create_app()) as client:
            resp = client.get("/api/v1/validate/history/entities/insights?limit=10")
            assert resp.status_code == 200
            session.rollback.assert_awaited_once()
