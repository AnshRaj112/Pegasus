# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:22:13Z
# --- END GENERATED FILE METADATA ---

"""Accuracy sweep across common file types for display-label detection."""

from __future__ import annotations

import gzip
import json
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from pegasus.validation.file_detection import detect_file
from pegasus.validation.file_detection.display_label import build_format_display_label


@dataclass(frozen=True)
class AccuracyCase:
    name: str
    expected_label: str
    expected_format: str | None = None
    builder: str = ""


def _write_fixed_width(path: Path) -> None:
    lines = [
        "ID      NAME                AMOUNT",
        "00000001ALICE SMITH          00001234",
        "00000002BOB JONES            00005678",
        "00000003CAROL WHITE          00009012",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_csv(path: Path) -> None:
    path.write_text("id,name,score\n1,alice,90\n2,bob,85\n", encoding="utf-8")


def _write_tsv(path: Path) -> None:
    path.write_text("id\tname\tscore\n1\talice\t90\n", encoding="utf-8")


def _write_json(path: Path) -> None:
    path.write_text(json.dumps({"id": 1, "name": "alice"}), encoding="utf-8")


def _write_jsonl(path: Path) -> None:
    path.write_text('{"id":1}\n{"id":2}\n', encoding="utf-8")


def _write_parquet(path: Path) -> None:
    path.write_bytes(b"PAR1" + b"\x00" * 200 + b"PAR1")


def _write_png(path: Path) -> None:
  # Minimal valid PNG header + IHDR chunk stub
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _write_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF")


def _write_xml(path: Path) -> None:
    path.write_text('<?xml version="1.0"?><root><item id="1"/></root>', encoding="utf-8")


def _write_yaml(path: Path) -> None:
    path.write_text("---\nid: 1\nname: alice\n", encoding="utf-8")


def _write_jpeg(path: Path) -> None:
    # JPEG SOI + EOI markers
    path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")


def _write_avro(path: Path) -> None:
    path.write_bytes(b"Obj\x01" + b"\x00" * 64)


def _write_orc(path: Path) -> None:
    path.write_bytes(b"ORC" + b"\x00" * 64)


def _write_dat_delimited(path: Path) -> None:
    path.write_text("col1,col2\nval1,val2\n", encoding="utf-8")


def _write_zip_csv(work: Path, archive_name: str) -> Path:
    inner = work / "inner.csv"
    _write_csv(inner)
    archive = work / archive_name
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(inner, arcname="data.csv")
    return archive


def _write_nested_zip_csv(work: Path) -> Path:
    inner_csv = work / "leaf.csv"
    _write_csv(inner_csv)
    inner_zip = work / "mid.zip"
    with zipfile.ZipFile(inner_zip, "w") as zf:
        zf.write(inner_csv, arcname="leaf.csv")
    outer = work / "nested.zip"
    with zipfile.ZipFile(outer, "w") as zf:
        zf.write(inner_zip, arcname="mid.zip")
    return outer


def _write_tar_csv(work: Path, archive_name: str) -> Path:
    inner = work / "inner.csv"
    _write_csv(inner)
    archive = work / archive_name
    with tarfile.open(archive, "w") as tf:
        tf.add(inner, arcname="rows.csv")
    return archive


def _write_gzip_csv(work: Path) -> Path:
    path = work / "data.csv.gz"
    payload = b"id,name\n1,alice\n"
    with gzip.open(path, "wb") as fh:
        fh.write(payload)
    return path


def _build_case(work: Path, case: AccuracyCase) -> Path:
    if case.builder == "fixed_width_dat":
        path = work / "payroll.dat"
        _write_fixed_width(path)
        return path
    if case.builder == "csv":
        path = work / "sample.csv"
        _write_csv(path)
        return path
    if case.builder == "tsv":
        path = work / "sample.tsv"
        _write_tsv(path)
        return path
    if case.builder == "json":
        path = work / "doc.json"
        _write_json(path)
        return path
    if case.builder == "jsonl":
        path = work / "stream.ndjson"
        _write_jsonl(path)
        return path
    if case.builder == "parquet":
        path = work / "table.parquet"
        _write_parquet(path)
        return path
    if case.builder == "png":
        path = work / "logo.png"
        _write_png(path)
        return path
    if case.builder == "pdf":
        path = work / "doc.pdf"
        _write_pdf(path)
        return path
    if case.builder == "xml":
        path = work / "feed.xml"
        _write_xml(path)
        return path
    if case.builder == "yaml":
        path = work / "config.yaml"
        _write_yaml(path)
        return path
    if case.builder == "jpeg":
        path = work / "photo.jpg"
        _write_jpeg(path)
        return path
    if case.builder == "avro":
        path = work / "events.avro"
        _write_avro(path)
        return path
    if case.builder == "orc":
        path = work / "table.orc"
        _write_orc(path)
        return path
    if case.builder == "dat_csv":
        path = work / "export.dat"
        _write_dat_delimited(path)
        return path
    if case.builder == "zip_csv":
        return _write_zip_csv(work, "bundle.zip")
    if case.builder == "nested_zip_csv":
        return _write_nested_zip_csv(work)
    if case.builder == "tar_csv":
        return _write_tar_csv(work, "bundle.tar")
    if case.builder == "gzip_csv":
        return _write_gzip_csv(work)
    if case.builder == "fixed_width_txt":
        path = work / "payroll.txt"
        _write_fixed_width(path)
        return path
    if case.builder == "delimited_txt":
        path = work / "data.txt"
        _write_csv(path)
        return path
    if case.builder == "plain_txt":
        path = work / "notes.txt"
        path.write_text("hello world\nno structure here\n", encoding="utf-8")
        return path
    if case.builder == "zip_fixed_width_txt":
        inner = work / "payroll.txt"
        _write_fixed_width(inner)
        archive = work / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.write(inner, arcname="payroll.txt")
        return archive
    raise ValueError(f"unknown builder {case.builder!r}")


ACCURACY_CASES: tuple[AccuracyCase, ...] = (
    AccuracyCase("fixed-width .txt", "fixed-width", "fixed-width", "fixed_width_txt"),
    AccuracyCase("delimited .txt", "csv", "csv", "delimited_txt"),
    AccuracyCase("plain .txt", "txt", None, "plain_txt"),
    AccuracyCase("zip -> fixed-width", "zip -> fixed-width", None, "zip_fixed_width_txt"),
    AccuracyCase("fixed-width .dat", "fixed-width", "fixed-width", "fixed_width_dat"),
    AccuracyCase("csv", "csv", "csv", "csv"),
    AccuracyCase("tsv", "tsv", "tsv", "tsv"),
    AccuracyCase("json document", "json", "json", "json"),
    AccuracyCase("jsonl / ndjson", "json", "json", "jsonl"),
    AccuracyCase("parquet", "parquet", "parquet", "parquet"),
    AccuracyCase("orc", "orc", "orc", "orc"),
    AccuracyCase("avro", "avro", "avro", "avro"),
    AccuracyCase("png image", "png", None, "png"),
    AccuracyCase("jpeg image", "jpeg", None, "jpeg"),
    AccuracyCase("pdf", "pdf", None, "pdf"),
    AccuracyCase("xml", "xml", None, "xml"),
    AccuracyCase("yaml", "yaml", None, "yaml"),
    AccuracyCase("delimited .dat", "csv", "csv", "dat_csv"),
    AccuracyCase("zip -> csv", "zip -> csv", None, "zip_csv"),
    AccuracyCase("zip -> zip -> csv", "zip -> zip -> csv", None, "nested_zip_csv"),
    AccuracyCase("tar -> csv", "tar -> csv", None, "tar_csv"),
    AccuracyCase("gzip -> csv", "gzip -> csv", None, "gzip_csv"),
)


@pytest.fixture(scope="module")
def accuracy_results() -> list[dict]:
    import tempfile

    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="pegasus-fmt-acc-") as tmp:
        work = Path(tmp)
        for case in ACCURACY_CASES:
            path = _build_case(work, case)
            report = detect_file(path)
            label = build_format_display_label(report, path=path, object_name=path.name)
            rows.append(
                {
                    "name": case.name,
                    "path": path.name,
                    "expected_label": case.expected_label,
                    "actual_label": label,
                    "expected_format": case.expected_format,
                    "actual_format": report.suggested_file_format,
                    "dataset_model": report.dataset_model,
                    "label_ok": label == case.expected_label,
                    "format_ok": (
                        case.expected_format is None
                        or report.suggested_file_format == case.expected_format
                    ),
                }
            )
    return rows


@pytest.mark.parametrize("case", ACCURACY_CASES, ids=[c.name for c in ACCURACY_CASES])
def test_format_detection_accuracy_case(tmp_path: Path, case: AccuracyCase) -> None:
    path = _build_case(tmp_path, case)
    report = detect_file(path)
    label = build_format_display_label(report, path=path, object_name=path.name)
    assert label == case.expected_label, (
        f"label mismatch for {case.name}: got {label!r}, want {case.expected_label!r}"
    )
    if case.expected_format is not None:
        assert report.suggested_file_format == case.expected_format, (
            f"format mismatch for {case.name}: "
            f"got {report.suggested_file_format!r}, want {case.expected_format!r}"
        )


def test_format_detection_accuracy_summary(accuracy_results: list[dict]) -> None:
    label_hits = sum(1 for row in accuracy_results if row["label_ok"])
    format_cases = [row for row in accuracy_results if row["expected_format"] is not None]
    format_hits = sum(1 for row in format_cases if row["format_ok"])
    label_acc = label_hits / len(accuracy_results)
    format_acc = format_hits / len(format_cases) if format_cases else 1.0

    print("\n=== Format detection accuracy ===")
    print(f"Display label accuracy: {label_hits}/{len(accuracy_results)} ({label_acc:.0%})")
    print(f"Suggested format accuracy: {format_hits}/{len(format_cases)} ({format_acc:.0%})")
    print(f"{'CASE':<22} {'EXPECTED':<20} {'ACTUAL':<20} {'LABEL':>5} {'FORMAT':>6}")
    for row in accuracy_results:
        fmt_mark = "OK" if row["format_ok"] else ("—" if row["expected_format"] is None else "MISS")
        print(
            f"{row['name']:<22} {row['expected_label']:<20} {row['actual_label']:<20} "
            f"{'OK' if row['label_ok'] else 'MISS':>5} {fmt_mark:>6}"
        )

    assert label_acc >= 0.85, f"label accuracy {label_acc:.0%} below 85% threshold"
    assert format_acc >= 0.85, f"format accuracy {format_acc:.0%} below 85% threshold"
