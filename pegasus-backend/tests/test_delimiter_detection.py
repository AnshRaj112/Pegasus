"""Tests for delimiter auto-detection (including alphabetic multi-char ``xx``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.validation.readers.delimiter_detection import (
    detect_delimiter,
    resolve_shared_auto_delimiter,
)


def _repo_test_data() -> Path:
    return Path(__file__).resolve().parents[2] / "test-data"


def test_detect_alphabetic_multichar_xx_delimiter(tmp_path: Path) -> None:
    path = tmp_path / "sample.csv"
    path.write_text(
        "idxxskuxxamountxxregion\n1xxSKU-00001xx101xxEMEA\n2xxSKU-00002xx102xxAPAC\n",
        encoding="utf-8",
    )
    result = detect_delimiter(path)
    assert result.delimiter == "xx"
    assert result.strategy == "heuristic-multi-char"


def test_detect_validation_fixture_files_auto_xx() -> None:
    root = _repo_test_data()
    source = root / "validation_source.csv"
    target = root / "validation_target.csv"
    if not source.is_file() or not target.is_file():
        pytest.skip("validation fixtures not present")
    assert detect_delimiter(source).delimiter == "xx"
    assert detect_delimiter(target).delimiter == "xx"
    shared = resolve_shared_auto_delimiter(source, target)
    assert shared.delimiter == "xx"


def test_preview_local_columns_validation_fixtures_four_columns(
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
                "uid_column": "id",
                "delimiter": "auto",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delimiter"] == "xx"
    assert body["source_columns"] == ["id", "sku", "amount", "region"]
    assert body["target_columns"] == ["id", "sku", "amount", "region"]
    assert body["compare_columns"] == ["sku", "amount", "region"]
    assert body["auto_mappings"] == [
        {"source_column": "sku", "target_column": "sku"},
        {"source_column": "amount", "target_column": "amount"},
        {"source_column": "region", "target_column": "region"},
    ]
