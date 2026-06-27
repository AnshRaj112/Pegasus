# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:50:11Z
# --- END GENERATED FILE METADATA ---

"""generated-100k fixture: manifest expectations and pipeline counts."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from pegasus.core.config import get_settings
from pegasus.services.validation_service import ValidationService

_REPO = Path("/home/ansh.raj/Pegasus")
_MANIFEST = _REPO / "test-data/generated-100k/manifest.json"
_SRC = _REPO / "test-data/generated-100k/source.csv"
_TGT = _REPO / "test-data/generated-100k/target.csv"


@pytest.mark.skipif(not _MANIFEST.is_file(), reason="generated-100k manifest missing")
def test_generated_100k_manifest_declares_four_columns() -> None:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["column_count"] == 4
    assert manifest["columns"] == ["id", "sku", "amount", "region"]
    assert manifest["delimiter"] == "||"
    assert manifest["source_rows"] == 100_000
    assert manifest["target_rows"] == 104_000
    assert manifest["total_mismatch_records"] == 8000


@pytest.mark.skipif(not _SRC.is_file(), reason="generated-100k CSVs missing")
def test_generated_100k_validates_under_ten_seconds() -> None:
    get_settings.cache_clear()
    service = ValidationService(get_settings())
    t0 = time.perf_counter()
    result = service._validate_csv_pair_sync(_SRC, _TGT, "id", "||")
    elapsed = time.perf_counter() - t0
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    assert result.source_row_count == manifest["source_rows"]
    assert result.target_row_count == manifest["target_rows"]
    total = sum(int(v) for v in result.report.summary.values())
    assert total == manifest["total_mismatch_records"]
    assert elapsed < 10.0, f"100k || validation took {elapsed:.2f}s"
