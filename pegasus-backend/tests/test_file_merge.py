"""Tests for multi-file merge before validation."""

from __future__ import annotations

import json
from pathlib import Path

from pegasus.validation.file_merge import merge_paths_for_format


def test_merge_csv_skips_extra_headers(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    out = tmp_path / "merged.csv"
    a.write_text("id,name\n1,Alice\n", encoding="utf-8")
    b.write_text("id,name\n2,Bob\n", encoding="utf-8")
    merge_paths_for_format([a, b], file_format="csv", destination=out, delimiter=",", has_header=True)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines == ["id,name", "1,Alice", "2,Bob"]


def test_merge_json_array_shards(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    out = tmp_path / "merged.json"
    a.write_text(json.dumps([{"id": 1}]), encoding="utf-8")
    b.write_text(json.dumps([{"id": 2}]), encoding="utf-8")
    merge_paths_for_format([a, b], file_format="json", destination=out)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc == [{"id": 1}, {"id": 2}]
