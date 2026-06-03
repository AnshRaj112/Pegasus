"""Tests for multi-layer file detection pipeline."""

from __future__ import annotations

import gzip
import json
import zipfile
from pathlib import Path

import pytest

from pegasus.validation.file_detection import detect_file
from pegasus.validation.file_detection.models import DatasetModel, ValidationStrategyHint
from pegasus.validation.file_detection.preflight_bridge import check_csv_prefix_bytes
from pegasus.validation.file_detection.sampling import SAMPLE_64K, read_file_sample
from pegasus.validation.preflight_errors import CsvPreflightError


@pytest.fixture
def tmp_csv(tmp_path: Path) -> Path:
    p = tmp_path / "data.csv"
    p.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    return p


def test_read_file_sample_bounded(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (SAMPLE_64K + 10_000))
    sample = read_file_sample(big)
    assert sample.bytes_read == SAMPLE_64K
    assert sample.file_size_bytes == SAMPLE_64K + 10_000


def test_detect_csv_tabular(tmp_csv: Path) -> None:
    report = detect_file(tmp_csv)
    assert report.dataset_model == DatasetModel.TABULAR
    assert report.structured_format is not None
    assert report.structured_format.detected_type in {"csv", "tsv", "psv"}
    assert report.suggested_file_format == "csv"
    assert report.bytes_read <= SAMPLE_64K


def test_detect_json(tmp_path: Path) -> None:
    p = tmp_path / "doc.json"
    p.write_text(json.dumps({"a": 1, "b": [2, 3]}), encoding="utf-8")
    report = detect_file(p)
    assert report.dataset_model == DatasetModel.HIERARCHICAL
    assert report.suggested_file_format == "json"


def test_detect_jsonl(tmp_path: Path) -> None:
    p = tmp_path / "lines.ndjson"
    p.write_text('{"x":1}\n{"x":2}\n{"x":3}\n', encoding="utf-8")
    report = detect_file(p)
    assert report.structured_format is not None
    assert report.structured_format.detected_type == "jsonl"


def test_detect_gzip_compression(tmp_path: Path) -> None:
    raw = tmp_path / "inner.csv"
    raw.write_text("a,b\n1,2\n", encoding="utf-8")
    gz = tmp_path / "data.csv.gz"
    gz.write_bytes(gzip.compress(raw.read_bytes()))
    report = detect_file(gz)
    assert report.compression is not None
    assert report.compression.detected_type == "gzip"
    assert report.validation_strategy is not None
    assert report.validation_strategy.detected_type == ValidationStrategyHint.DECOMPRESS_FIRST.value


def test_detect_zip_container(tmp_path: Path) -> None:
    zpath = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("nested/report.csv", "h1,h2\n1,2\n")
    report = detect_file(zpath)
    assert report.dataset_model == DatasetModel.CONTAINER
    assert report.container is not None
    assert report.container.detected_type == "zip"
    assert report.container.metadata.get("entry_count", 0) >= 1


def test_user_format_hint_overrides(tmp_csv: Path) -> None:
    report = detect_file(tmp_csv, user_format_hint="json")
    assert report.suggested_file_format == "json"


def test_preflight_bridge_gzip_raises() -> None:
    with pytest.raises(CsvPreflightError, match="gzip"):
        check_csv_prefix_bytes(b"\x1f\x8b\x08", label="source")


def test_preflight_bridge_utf16_raises() -> None:
    with pytest.raises(CsvPreflightError, match="UTF-16"):
        check_csv_prefix_bytes(b"\xff\xfe", label="target")


def test_extension_content_mismatch_warning(tmp_path: Path) -> None:
    p = tmp_path / "report.csv"
    p.write_text('{"not": "csv"}\n', encoding="utf-8")
    report = detect_file(p)
    assert any("extension" in w for w in report.warnings) or report.structured_format.detected_type == "json"
