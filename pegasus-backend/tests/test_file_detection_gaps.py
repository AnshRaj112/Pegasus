"""Tests for remaining file-detection gaps (auto-routing, archives, columnar, plugins)."""

from __future__ import annotations

import gzip
import json
import zipfile
from pathlib import Path

import polars as pl
import pytest

from pegasus.validation.file_detection.archive_extract import (
    ArchiveExtractError,
    materialize_validation_path,
)
from pegasus.validation.file_detection.delimiter_bridge import resolve_auto_delimiter
from pegasus.validation.file_detection.plugins.registry import (
    RegisteredFormatPlugin,
    get_format_plugin,
    register_format_plugin,
)
from pegasus.validation.file_detection.routing import (
    coerce_local_validate_fields_with_detection,
    is_auto_format,
)
from pegasus.validation.fixed_width_meta import is_columnar_run, normalize_file_format


def test_is_auto_format() -> None:
    assert is_auto_format("auto")
    assert is_auto_format("detect")
    assert not is_auto_format("csv")


def test_materialize_gzip(tmp_path: Path) -> None:
    inner = tmp_path / "data.csv"
    inner.write_text("a,b\n1,2\n", encoding="utf-8")
    gz = tmp_path / "wrap.csv.gz"
    gz.write_bytes(gzip.compress(inner.read_bytes()))
    mat = materialize_validation_path(gz, work_dir=tmp_path / "work")
    assert mat.path.read_text(encoding="utf-8").startswith("a,b")
    assert mat.warnings


def test_materialize_zip(tmp_path: Path) -> None:
    zpath = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("inner/report.csv", "id,v\n10,20\n")
    mat = materialize_validation_path(zpath, work_dir=tmp_path / "work")
    assert "10,20" in mat.path.read_text(encoding="utf-8")


def test_archive_bomb_limit(tmp_path: Path) -> None:
    zpath = tmp_path / "big.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("huge.csv", "x" * 2000)
    with pytest.raises(ArchiveExtractError):
        materialize_validation_path(zpath, max_extract_bytes=500, work_dir=tmp_path / "w")


def test_coerce_auto_detect_json(tmp_path: Path) -> None:
    src = tmp_path / "a.json"
    tgt = tmp_path / "b.json"
    src.write_text('{"k": 1}', encoding="utf-8")
    tgt.write_text('{"k": 2}', encoding="utf-8")
    fmt, delim, cfg, _, _, _, warnings = coerce_local_validate_fields_with_detection(
        file_format="auto",
        delimiter="auto",
        fixed_width_config=None,
        column_mappings=None,
        source_path=src,
        target_path=tgt,
        auto_detect=True,
        auto_extract=False,
    )
    assert fmt == "json"
    assert delim == "json"
    assert cfg is None


def test_coerce_auto_extract_zip(tmp_path: Path) -> None:
    src = tmp_path / "s.zip"
    tgt = tmp_path / "t.zip"
    for zpath, rows in ((src, "1,a\n"), (tgt, "1,b\n")):
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr("d.csv", f"id,name\n{rows}")
    fmt, _, _, out_src, out_tgt, cleanup, _ = coerce_local_validate_fields_with_detection(
        file_format="auto",
        delimiter="auto",
        fixed_width_config=None,
        column_mappings=None,
        source_path=src,
        target_path=tgt,
        auto_detect=True,
        auto_extract=True,
        work_dir=tmp_path / "job",
    )
    assert fmt == "csv"
    assert out_src.is_file()
    assert out_tgt.is_file()
    assert cleanup


def test_resolve_auto_delimiter_from_detection(tmp_path: Path) -> None:
    p1 = tmp_path / "one.csv"
    p2 = tmp_path / "two.csv"
    p1.write_text("a|b|c\n1|2|3\n4|5|6\n", encoding="utf-8")
    p2.write_text("a|b|c\n7|8|9\n", encoding="utf-8")
    assert resolve_auto_delimiter(p1, p2) == "|"


def test_columnar_format_tokens() -> None:
    assert normalize_file_format("parquet") == "parquet"
    assert is_columnar_run("parquet")
    assert is_columnar_run("excel")


def test_parquet_validation(tmp_path: Path) -> None:
    from pegasus.core.config import get_settings
    from pegasus.services.validation_service import ValidationService

    src = tmp_path / "s.parquet"
    tgt = tmp_path / "t.parquet"
    pl.DataFrame({"id": [1], "v": ["a"]}).write_parquet(src)
    pl.DataFrame({"id": [1], "v": ["b"]}).write_parquet(tgt)
    svc = ValidationService(settings=get_settings())
    result = svc.validate_columnar_pair_sync(src, tgt, uid_column="id", file_format="parquet")
    assert result.source_row_count == 1
    assert result.report.summary.get("value_mismatch", 0) >= 1 or sum(result.report.summary.values()) >= 1


def test_plugin_registry_custom() -> None:
    register_format_plugin(
        RegisteredFormatPlugin(
            "custom_fmt",
            frozenset({".cst"}),
            file_format_token="csv",
            detect_fn=lambda _s: None,
        ),
        replace=True,
    )
    assert get_format_plugin("custom_fmt") is not None
