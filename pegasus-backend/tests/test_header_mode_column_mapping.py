"""Header vs headerless column naming and name-based auto-mapping."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.services.validation_job_queue import reset_validation_queue


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    reset_validation_queue()
    yield
    get_settings.cache_clear()
    reset_validation_queue()


def test_preview_with_header_uses_column_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    src = tmp_path / "s.csv"
    tgt = tmp_path / "t.csv"
    src.write_text("id,name,city\n1,alice,paris\n2,bob,rome\n", encoding="utf-8")
    tgt.write_text("id,name,city\n1,alice,paris\n2,bob,lyon\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        r = client.get(
            "/api/v1/validate/local/columns",
            params={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": ",",
                "has_header": "true",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_header"] is True
    assert body["inferred_has_header"] is True
    assert body["source_columns"] == ["id", "name", "city"]
    assert body["auto_mappings"] == [
        {"source_column": "name", "target_column": "name"},
        {"source_column": "city", "target_column": "city"},
    ]


def test_preview_headerless_does_not_use_first_row_as_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    src = tmp_path / "s.csv"
    tgt = tmp_path / "t.csv"
    src.write_text("1,alice,paris\n2,bob,rome\n", encoding="utf-8")
    tgt.write_text("1,alice,paris\n2,bob,lyon\n", encoding="utf-8")

    with TestClient(create_app()) as client:
        r = client.get(
            "/api/v1/validate/local/columns",
            params={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "column_1",
                "delimiter": ",",
                "has_header": "false",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_header"] is False
    assert body["inferred_has_header"] is False
    assert body["source_columns"] == ["column_1", "column_2", "column_3"]
    assert "alice" not in body["source_columns"]
