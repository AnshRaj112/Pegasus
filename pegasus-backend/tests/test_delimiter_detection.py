"""Tests for delimiter auto-detection (including alphabetic multi-char ``xx``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pegasus.core.config import get_settings
from pegasus.main import create_app
from pegasus.validation.readers.delimiter_detection import (
    detect_delimiter,
    polars_supports_csv_delimiter,
    resolve_shared_auto_delimiter,
)


def _repo_test_data() -> Path:
    return Path(__file__).resolve().parents[2] / "test-data"


def test_polars_supports_csv_delimiter_single_byte_only() -> None:
    assert polars_supports_csv_delimiter(",")
    assert polars_supports_csv_delimiter("\t")
    assert not polars_supports_csv_delimiter("xx")
    assert not polars_supports_csv_delimiter("||")
    assert not polars_supports_csv_delimiter("🚀")


def test_preview_local_columns_emoji_delimiter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    delim = "🚀"
    src = tmp_path / "source.csv"
    tgt = tmp_path / "target.csv"
    src.write_text(f"id{delim}name{delim}score\n1{delim}alice{delim}9\n", encoding="utf-8")
    tgt.write_text(f"id{delim}name{delim}score\n1{delim}alice{delim}10\n", encoding="utf-8")

    monkeypatch.setenv("PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS", "true")
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get(
            "/api/v1/validate/local/columns",
            params={
                "source_path": str(src),
                "target_path": str(tgt),
                "uid_column": "id",
                "delimiter": delim,
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delimiter"] == delim
    assert body["source_columns"] == ["id", "name", "score"]
    assert body["target_columns"] == ["id", "name", "score"]


def test_detect_comma_delimiter_structured_compare_fixture() -> None:
    """Comma CSV with quoted JSON; auto must not pick ``ta`` from column names."""
    root = _repo_test_data()
    source = root / "structured-compare" / "csv" / "source.csv"
    if not source.is_file():
        pytest.skip("structured-compare fixtures not present")
    assert detect_delimiter(source).delimiter == ","
    shared = resolve_shared_auto_delimiter(source, source)
    assert shared.delimiter == ","


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
    assert detect_delimiter(source).delimiter == r"~\^|~"
    assert detect_delimiter(target).delimiter == r"~\^|~"
    shared = resolve_shared_auto_delimiter(source, target)
    assert shared.delimiter == r"~\^|~"


def test_detect_delimiter_uses_bounded_prefix(tmp_path: Path) -> None:
    path = tmp_path / "bounded.csv"
    with path.open("w", encoding="utf-8") as f:
        for i in range(2000):
            f.write(f"id,sku,amount\n{i},SKU-{i:05d},{100+i}\n")
        # Contradictory tail should not dominate detection for bounded prefix.
        for i in range(2000):
            f.write(f"id;sku;amount\n{i};SKU-{i:05d};{100+i}\n")
    out = detect_delimiter(path)
    assert out.delimiter == ","


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
                "uid_column": "column_1",
                "delimiter": "auto",
                "has_header": "false",
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delimiter"] == r"~\^|~"
    assert body["has_header"] is False
    assert body["inferred_has_header"] is False
    assert body["source_columns"] == ["column_1", "column_2", "column_3", "column_4"]
    assert body["target_columns"] == ["column_1", "column_2", "column_3", "column_4"]
    assert body["compare_columns"] == ["column_2", "column_3", "column_4"]
    assert body["auto_mappings"] == [
        {"source_column": "column_2", "target_column": "column_2"},
        {"source_column": "column_3", "target_column": "column_3"},
        {"source_column": "column_4", "target_column": "column_4"},
    ]
