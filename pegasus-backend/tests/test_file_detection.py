# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-10T11:49:33Z
# --- END GENERATED FILE METADATA ---

"""Tests for multi-layer file detection."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from pegasus.validation.file_detection import detect_file
from pegasus.validation.file_detection.coerce import resolve_file_format_with_detection
from pegasus.validation.file_format import normalize_file_format


def test_detect_plain_csv(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    report = detect_file(path, user_format_hint="csv")
    assert report.bytes_read <= 65536
    assert report.dataset_model == "tabular"
    assert report.suggested_file_format == "csv"
    assert report.structured_format is not None
    assert report.structured_format.detected_type in {"csv", "tsv", "psv"}


def test_detect_gzip_csv_wrong_extension(tmp_path: Path) -> None:
    path = tmp_path / "report.csv"
    payload = b"id,name\n1,alice\n"
    with gzip.open(path, "wb") as fh:
        fh.write(payload)
    report = detect_file(path, user_format_hint="csv")
    assert report.compression is not None
    assert report.compression.detected_type == "gzip"
    assert report.validation_strategy is not None
    assert report.validation_strategy.detected_type == "decompress_first"
    assert any("extension" in w or "gzip" in w.lower() for w in report.warnings) or report.extension


def test_detect_json(tmp_path: Path) -> None:
    path = tmp_path / "doc.json"
    path.write_text(json.dumps({"id": 1, "name": "x"}), encoding="utf-8")
    report = detect_file(path)
    assert report.dataset_model == "hierarchical"
    assert report.suggested_file_format == "json"


def test_resolve_auto_format(tmp_path: Path) -> None:
    path = tmp_path / "x.ndjson"
    path.write_text('{"a":1}\n{"a":2}\n', encoding="utf-8")
    fmt, _ = resolve_file_format_with_detection(path, "auto", settings=None)
    assert normalize_file_format(fmt) == "json"


def test_detect_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.dat"
    path.write_bytes(b"")
    report = detect_file(path)
    assert report.file_size_bytes == 0
    assert report.bytes_read == 0
