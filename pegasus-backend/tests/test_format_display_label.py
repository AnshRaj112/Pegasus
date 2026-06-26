# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T15:09:23+05:30
# --- END GENERATED FILE METADATA ---

"""Tests for format display labels and fixed-width detection."""

from __future__ import annotations

import zipfile
from pathlib import Path

from pegasus.validation.file_detection import detect_file
from pegasus.validation.file_detection.display_label import build_format_display_label


def _write_fixed_width(path: Path) -> None:
    lines = [
        "ID      NAME                AMOUNT",
        "00000001ALICE SMITH          00001234",
        "00000002BOB JONES            00005678",
        "00000003CAROL WHITE          00009012",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_detect_fixed_width_dat(tmp_path: Path) -> None:
    path = tmp_path / "payroll.dat"
    _write_fixed_width(path)
    report = detect_file(path)
    assert report.suggested_file_format == "fixed-width"
    assert build_format_display_label(report, path=path) == "fixed-width"


def test_display_label_fixed_width_txt(tmp_path: Path) -> None:
    path = tmp_path / "payroll.txt"
    _write_fixed_width(path)
    report = detect_file(path)
    assert report.suggested_file_format == "fixed-width"
    assert build_format_display_label(report, path=path) == "fixed-width"


def test_display_label_delimited_dat(tmp_path: Path) -> None:
    path = tmp_path / "export.dat"
    path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    report = detect_file(path)
    assert build_format_display_label(report, path=path, object_name=path.name) == "dat"
    assert report.suggested_file_format == "csv"


def test_display_label_delimited_txt(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("id,name\n1,alice\n2,bob\n", encoding="utf-8")
    report = detect_file(path)
    assert report.suggested_file_format == "csv"
    assert build_format_display_label(report, path=path) == "csv"


def test_display_label_plain_txt(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("hello world\nno structure here\n", encoding="utf-8")
    report = detect_file(path)
    assert build_format_display_label(report, path=path) == "txt"


def test_display_label_zip_contains_fixed_width_txt(tmp_path: Path) -> None:
    inner = tmp_path / "payroll.txt"
    _write_fixed_width(inner)
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(inner, arcname="payroll.txt")
    report = detect_file(archive)
    label = build_format_display_label(report, path=archive, object_name=archive.name)
    assert label == "zip -> fixed-width"


def test_display_label_tar_contains_fixed_width_txt(tmp_path: Path) -> None:
    import tarfile

    inner = tmp_path / "payroll.txt"
    _write_fixed_width(inner)
    archive = tmp_path / "bundle.tar"
    with tarfile.open(archive, "w") as tf:
        tf.add(inner, arcname="payroll.txt")
    report = detect_file(archive)
    label = build_format_display_label(report, path=archive, object_name=archive.name)
    assert label == "tar -> fixed-width"


def test_display_label_parquet(tmp_path: Path) -> None:
    path = tmp_path / "table.parquet"
    path.write_bytes(b"PAR1" + b"\x00" * 100)
    report = detect_file(path)
    label = build_format_display_label(report, path=path, object_name=path.name)
    assert label == "parquet"


def test_display_label_zip_contains_csv(tmp_path: Path) -> None:
    inner = tmp_path / "data.csv"
    inner.write_text("id,name\n1,alice\n", encoding="utf-8")
    archive = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(inner, arcname="data.csv")
    report = detect_file(archive)
    label = build_format_display_label(report, path=archive, object_name=archive.name)
    assert label == "zip -> csv"


def test_display_label_nested_zip_contains_csv(tmp_path: Path) -> None:
    inner_csv = tmp_path / "records.csv"
    inner_csv.write_text("id\n1\n", encoding="utf-8")
    inner_zip = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner_zip, "w") as zf:
        zf.write(inner_csv, arcname="records.csv")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as zf:
        zf.write(inner_zip, arcname="inner.zip")
    report = detect_file(outer)
    label = build_format_display_label(report, path=outer, object_name=outer.name)
    assert label == "zip -> zip -> csv"


def test_display_label_tar_contains_csv(tmp_path: Path) -> None:
    import tarfile

    inner = tmp_path / "rows.csv"
    inner.write_text("a,b\n1,2\n", encoding="utf-8")
    archive = tmp_path / "bundle.tar"
    with tarfile.open(archive, "w") as tf:
        tf.add(inner, arcname="rows.csv")
    report = detect_file(archive)
    label = build_format_display_label(report, path=archive, object_name=archive.name)
    assert label == "tar -> csv"


def test_display_label_from_nested_archive_member_path() -> None:
    from pegasus.validation.file_detection.display_label import (
        format_chain_from_archive_member_path,
        format_display_label_from_archive_members,
    )

    chain = format_chain_from_archive_member_path("inner.tar/bundle.zip/rows.csv", outer="tar")
    assert chain == ["tar", "tar", "zip", "csv"]

    label = format_display_label_from_archive_members(
        ["inner.tar/bundle.zip/rows.csv"],
        outer="tar",
    )
    assert label == "tar -> tar -> zip -> csv"


def test_infer_format_chain_from_case12_folder_name() -> None:
    from pegasus.validation.file_detection.display_label import infer_format_chain_from_object_name

    path = (
        "test-data/Test_Files/generated_tar_containing_tar_containing_zip_containing_csv_file/"
        "case12_src.tar"
    )
    assert infer_format_chain_from_object_name(path, outer="tar") == "tar -> tar -> zip -> csv"


def test_display_label_from_object_name_when_archive_not_readable(tmp_path: Path) -> None:
    from pegasus.validation.file_detection.types import FileDetectionReport
    from pegasus.validation.file_detection.layers import container as container_layer
    from pegasus.validation.file_detection.layers import magic_bytes as magic_layer
    from pegasus.validation.file_detection.sample import read_file_sample

    archive = tmp_path / "report.csv.zip"
    archive.write_bytes(b"PK\x03\x04" + b"\x00" * 32)
    sample = read_file_sample(archive, max_bytes=64)
    magic = magic_layer.detect_magic_bytes(sample)
    container = container_layer.detect_container(sample, magic)
    stub = FileDetectionReport(
        path=str(archive),
        file_size_bytes=archive.stat().st_size,
        bytes_read=sample.bytes_read,
        dataset_model="container",
        container=container,
        magic_bytes=magic,
    )
    label = build_format_display_label(stub, path=Path("report.csv.zip"), object_name="report.csv.zip")
    assert label == "zip -> csv"
