# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-27T14:34:06Z
# --- END GENERATED FILE METADATA ---

"""Tests for safe archive validation (no member decompression)."""

from __future__ import annotations

import tarfile
import time
import zipfile
from pathlib import Path

import pytest

from format_detection_cases import _write_csv, _zip_member, _tar_member
from pegasus.core.config import Settings
from pegasus.services.validation_service import ValidationService
from pegasus.validation.archive_compare import (
    assert_archive_headers_safe,
    archive_side_from_path,
    compare_archive_manifests,
    iter_tar_manifest,
    iter_zip_manifest,
    validate_archive_pair,
)
from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.file_detection import detect_file


def _settings() -> Settings:
    return Settings(
        validation_archive_max_declared_bytes=50 * 1024**3,
        validation_archive_max_compression_ratio=1000.0,
    )


def test_identical_zip_byte_and_manifest_match(tmp_path: Path) -> None:
    src = _zip_member(tmp_path, "a.zip", "data.csv", _write_csv)
    tgt = _zip_member(tmp_path, "b.zip", "data.csv", _write_csv)
    side_a = archive_side_from_path(src, archive_format="zip")
    side_b = archive_side_from_path(tgt, archive_format="zip")
    report = validate_archive_pair(
        side_a,
        side_b,
        max_declared_bytes=_settings().validation_archive_max_declared_bytes,
        max_compression_ratio=_settings().validation_archive_max_compression_ratio,
    )
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 0


def test_zip_entry_name_mismatch(tmp_path: Path) -> None:
    src = _zip_member(tmp_path, "a.zip", "alpha.csv", _write_csv)
    tgt = _zip_member(tmp_path, "b.zip", "beta.csv", _write_csv)
    src_entries = iter_zip_manifest(src)
    tgt_entries = iter_zip_manifest(tgt)
    report = compare_archive_manifests(src_entries, tgt_entries)
    assert report.summary[MismatchType.MISSING_IN_TARGET.value] >= 1
    assert report.summary[MismatchType.EXTRA_IN_TARGET.value] >= 1


def test_zip_missing_extra_entries(tmp_path: Path) -> None:
    one = tmp_path / "one.zip"
    two = tmp_path / "two.zip"
    with zipfile.ZipFile(one, "w") as zf:
        zf.writestr("a.csv", "id\n1\n")
    with zipfile.ZipFile(two, "w") as zf:
        zf.writestr("a.csv", "id\n1\n")
        zf.writestr("b.csv", "id\n2\n")
    report = compare_archive_manifests(iter_zip_manifest(one), iter_zip_manifest(two))
    assert report.summary[MismatchType.EXTRA_IN_TARGET.value] == 1


def test_zip_crc_metadata_mismatch(tmp_path: Path) -> None:
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    with zipfile.ZipFile(a, "w") as zf:
        zf.writestr("rows.csv", "id,name\n1,alice\n")
    with zipfile.ZipFile(b, "w") as zf:
        zf.writestr("rows.csv", "id,name\n1,bob\n")
    report = compare_archive_manifests(iter_zip_manifest(a), iter_zip_manifest(b))
    assert report.summary[MismatchType.VALUE_MISMATCH.value] >= 1


def test_zip_bomb_guard_rejects_declared_size() -> None:
    from pegasus.validation.archive_compare import ArchiveEntry

    bomb = ArchiveEntry(
        path="bomb.txt",
        compressed_size=1024,
        uncompressed_size=20 * 1024**3,
        crc32=0,
        compress_type=8,
        mtime=None,
        is_dir=False,
    )
    with pytest.raises(ValueError, match="declared uncompressed size"):
        assert_archive_headers_safe([bomb], max_declared_bytes=1024**3, max_compression_ratio=1000.0)


def test_tar_manifest_match(tmp_path: Path) -> None:
    src = _tar_member(tmp_path, "a.tar", "rows.csv", _write_csv)
    tgt = _tar_member(tmp_path, "b.tar", "rows.csv", _write_csv)
    report = validate_archive_pair(
        archive_side_from_path(src, archive_format="tar"),
        archive_side_from_path(tgt, archive_format="tar"),
        max_declared_bytes=_settings().validation_archive_max_declared_bytes,
        max_compression_ratio=_settings().validation_archive_max_compression_ratio,
    )
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 0
    assert len(iter_tar_manifest(src)) >= 1


def test_detection_suggests_zip_for_container(tmp_path: Path) -> None:
    path = _zip_member(tmp_path, "bundle.zip", "data.csv", _write_csv)
    report = detect_file(path)
    assert report.suggested_file_format == "zip"
    assert report.dataset_model == "container"


def test_validation_service_archive_integration(tmp_path: Path) -> None:
    src = _zip_member(tmp_path, "src.zip", "data.csv", _write_csv)
    tgt = _zip_member(tmp_path, "tgt.zip", "data.csv", _write_csv)
    service = ValidationService(_settings())
    result = service.validate_archive_pair_sync(src, tgt, file_format="zip")
    assert result.source_row_count >= 1
    assert result.report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 0


def test_nested_zip_zip_csv_manifest(tmp_path: Path) -> None:
    from format_detection_cases import _nested_zip_csv

    src_dir = tmp_path / "src"
    tgt_dir = tmp_path / "tgt"
    src_dir.mkdir()
    tgt_dir.mkdir()
    src = _nested_zip_csv(src_dir, depth=2)
    tgt = _nested_zip_csv(tgt_dir, depth=2)
    src_entries = iter_zip_manifest(src)
    tgt_entries = iter_zip_manifest(tgt)
    src_paths = {e.path for e in src_entries if not e.is_dir}
    tgt_paths = {e.path for e in tgt_entries if not e.is_dir}
    assert any(p.endswith("leaf.csv") for p in src_paths)
    assert src_paths == tgt_paths
    report = validate_archive_pair(
        archive_side_from_path(src, archive_format="zip"),
        archive_side_from_path(tgt, archive_format="zip"),
        max_declared_bytes=_settings().validation_archive_max_declared_bytes,
        max_compression_ratio=_settings().validation_archive_max_compression_ratio,
    )
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 0


def test_nested_tar_tar_csv_manifest(tmp_path: Path) -> None:
    import tarfile

    def _tar_tar_csv(work: Path) -> Path:
        csv_path = work / "leaf.csv"
        _write_csv(csv_path)
        inner_tar = work / "inner.tar"
        with tarfile.open(inner_tar, "w") as tf:
            tf.add(csv_path, arcname="data.csv")
        outer = work / "outer.tar"
        with tarfile.open(outer, "w") as tf:
            tf.add(inner_tar, arcname="inner.tar")
        return outer

    src_dir = tmp_path / "src"
    tgt_dir = tmp_path / "tgt"
    src_dir.mkdir()
    tgt_dir.mkdir()
    src = _tar_tar_csv(src_dir)
    tgt = _tar_tar_csv(tgt_dir)
    src_entries = iter_tar_manifest(src)
    assert any(e.path == "inner.tar/data.csv" for e in src_entries)
    report = validate_archive_pair(
        archive_side_from_path(src, archive_format="tar"),
        archive_side_from_path(tgt, archive_format="tar"),
        max_declared_bytes=_settings().validation_archive_max_declared_bytes,
        max_compression_ratio=_settings().validation_archive_max_compression_ratio,
    )
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 0


def test_nested_tar_zip_csv_manifest(tmp_path: Path) -> None:
    import tarfile

    def _tar_zip_csv(work: Path) -> Path:
        csv_path = work / "leaf.csv"
        _write_csv(csv_path)
        inner_zip = work / "bundle.zip"
        with zipfile.ZipFile(inner_zip, "w") as zf:
            zf.write(csv_path, arcname="rows.csv")
        outer = work / "outer.tar"
        with tarfile.open(outer, "w") as tf:
            tf.add(inner_zip, arcname="bundle.zip")
        return outer

    src_dir = tmp_path / "src"
    tgt_dir = tmp_path / "tgt"
    src_dir.mkdir()
    tgt_dir.mkdir()
    src = _tar_zip_csv(src_dir)
    tgt = _tar_zip_csv(tgt_dir)
    src_entries = iter_tar_manifest(src)
    assert any(e.path == "bundle.zip/rows.csv" for e in src_entries)
    report = validate_archive_pair(
        archive_side_from_path(src, archive_format="tar"),
        archive_side_from_path(tgt, archive_format="tar"),
        max_declared_bytes=_settings().validation_archive_max_declared_bytes,
        max_compression_ratio=_settings().validation_archive_max_compression_ratio,
    )
    assert report.summary.get(MismatchType.VALUE_MISMATCH.value, 0) == 0


def test_nested_inner_csv_mismatch(tmp_path: Path) -> None:
    import tarfile

    def _tar_with_csv(work: Path, csv_name: str) -> Path:
        csv_path = work / "leaf.csv"
        _write_csv(csv_path)
        inner_tar = work / "inner.tar"
        with tarfile.open(inner_tar, "w") as tf:
            tf.add(csv_path, arcname=csv_name)
        outer = work / "outer.tar"
        with tarfile.open(outer, "w") as tf:
            tf.add(inner_tar, arcname="inner.tar")
        return outer

    src_dir = tmp_path / "src"
    tgt_dir = tmp_path / "tgt"
    src_dir.mkdir()
    tgt_dir.mkdir()
    src = _tar_with_csv(src_dir, "data.csv")
    tgt = _tar_with_csv(tgt_dir, "other.csv")
    report = validate_archive_pair(
        archive_side_from_path(src, archive_format="tar"),
        archive_side_from_path(tgt, archive_format="tar"),
        max_declared_bytes=_settings().validation_archive_max_declared_bytes,
        max_compression_ratio=_settings().validation_archive_max_compression_ratio,
    )
    assert report.summary[MismatchType.MISSING_IN_TARGET.value] >= 1
    assert report.summary[MismatchType.EXTRA_IN_TARGET.value] >= 1


def test_zip_manifest_performance_1000_entries(tmp_path: Path) -> None:
    path = tmp_path / "many.zip"
    with zipfile.ZipFile(path, "w") as zf:
        for i in range(1000):
            zf.writestr(f"file_{i:04d}.txt", f"payload-{i}")
    start = time.perf_counter()
    entries = iter_zip_manifest(path)
    elapsed = time.perf_counter() - start
    assert len(entries) == 1000
    assert elapsed < 2.0
