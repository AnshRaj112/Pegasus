# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T05:26:33Z
# --- END GENERATED FILE METADATA ---

"""Fixture builders and expected outcomes for format-detection accuracy sweeps."""

from __future__ import annotations

import bz2
import gzip
import json
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

Builder = Callable[[Path], Path]


@dataclass(frozen=True)
class AccuracyCase:
    name: str
    expected_label: str
    expected_format: str | None = None
    builder: str = ""
    category: str = "other"


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _write_fixed_width(path: Path) -> None:
    lines = [
        "ID      NAME                AMOUNT",
        "00000001ALICE SMITH          00001234",
        "00000002BOB JONES            00005678",
        "00000003CAROL WHITE          00009012",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_csv(path: Path, *, delimiter: str = ",") -> None:
    d = delimiter
    path.write_text(f"id{d}name{d}score\n1{d}alice{d}90\n2{d}bob{d}85\n", encoding="utf-8")


def _write_tsv(path: Path) -> None:
    _write_csv(path, delimiter="\t")


def _write_psv(path: Path) -> None:
    _write_csv(path, delimiter="|")


def _write_json_object(path: Path) -> None:
    path.write_text(json.dumps({"id": 1, "name": "alice", "active": True}), encoding="utf-8")


def _write_json_array(path: Path) -> None:
    path.write_text(json.dumps([{"id": 1}, {"id": 2}]), encoding="utf-8")


def _write_jsonl(path: Path) -> None:
    path.write_text('{"id":1,"name":"a"}\n{"id":2,"name":"b"}\n{"id":3,"name":"c"}\n', encoding="utf-8")


def _write_parquet(path: Path) -> None:
    path.write_bytes(b"PAR1" + b"\x00" * 200 + b"PAR1")


def _write_orc(path: Path) -> None:
    path.write_bytes(b"ORC" + b"\x00" * 64)


def _write_avro(path: Path) -> None:
    path.write_bytes(b"Obj\x01" + b"\x00" * 64)


def _write_png(path: Path) -> None:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        b"\x90wS\xde"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _write_jpeg(path: Path) -> None:
    path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9")


def _write_gif(path: Path) -> None:
    path.write_bytes(
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00"
        b"!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    )


def _write_webp(path: Path) -> None:
    path.write_bytes(b"RIFF\x24\x00\x00\x00WEBPVP8 ")


def _write_bmp(path: Path) -> None:
    # 1x1 24-bit BMP
    path.write_bytes(
        b"BM"  # signature
        + (62).to_bytes(4, "little")  # file size
        + b"\x00\x00\x00\x00"  # reserved
        + (54).to_bytes(4, "little")  # pixel offset
        + (40).to_bytes(4, "little")  # DIB header size
        + (1).to_bytes(4, "little")  # width
        + (1).to_bytes(4, "little")  # height
        + (1).to_bytes(2, "little")  # planes
        + (24).to_bytes(2, "little")  # bpp
        + b"\x00" * 24  # rest of header + pixel
    )


def _write_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF")


def _write_xml(path: Path) -> None:
    path.write_text('<?xml version="1.0"?><catalog><item id="1">a</item></catalog>', encoding="utf-8")


def _write_yaml(path: Path) -> None:
    path.write_text("---\nid: 1\nname: alice\nroles:\n  - admin\n", encoding="utf-8")


def _write_html(path: Path) -> None:
    path.write_text("<!DOCTYPE html><html><body><p>hello</p></body></html>", encoding="utf-8")


def _write_svg(path: Path) -> None:
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>', encoding="utf-8")


def _write_plain_text(path: Path) -> None:
    path.write_text("hello world\nno tabular structure in this file\n", encoding="utf-8")


def _write_log_text(path: Path) -> None:
    path.write_text(
        "2024-01-01T10:00:00 INFO service started\n"
        "2024-01-01T10:05:00 WARN retry scheduled\n"
        "2024-01-01T10:10:00 INFO service stopped\n",
        encoding="utf-8",
    )


def _write_binary_blob(path: Path) -> None:
    path.write_bytes(bytes(range(256)) * 4)


def _write_sqlite(path: Path) -> None:
    path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 64)


def _zip_member(work: Path, archive_name: str, member_name: str, writer: Callable[[Path], None]) -> Path:
    inner = work / member_name.replace("/", "_")
    writer(inner)
    archive = work / archive_name
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(inner, arcname=member_name)
    return archive


def _tar_member(work: Path, archive_name: str, member_name: str, writer: Callable[[Path], None]) -> Path:
    inner = work / member_name.replace("/", "_")
    writer(inner)
    archive = work / archive_name
    with tarfile.open(archive, "w") as tf:
        tf.add(inner, arcname=member_name)
    return archive


def _gzip_file(work: Path, name: str, payload: bytes) -> Path:
    path = work / name
    with gzip.open(path, "wb") as fh:
        fh.write(payload)
    return path


def _bz2_file(work: Path, name: str, payload: bytes) -> Path:
    path = work / name
    path.write_bytes(bz2.compress(payload))
    return path


def _nested_zip_csv(work: Path, depth: int, archive_name: str = "nested.zip") -> Path:
    csv_path = work / "leaf.csv"
    _write_csv(csv_path)
    current = csv_path
    for level in range(depth):
        zpath = work / f"level{level}.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.write(current, arcname=current.name)
        current = zpath
    return work / f"level{depth - 1}.zip" if depth > 0 else csv_path


# ---------------------------------------------------------------------------
# Builders registry
# ---------------------------------------------------------------------------

def _b(work: Path, rel: str, writer: Callable[[Path], None]) -> Path:
    path = work / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    writer(path)
    return path


BUILDERS: dict[str, Builder] = {
    # --- delimited ---
    "csv": lambda w: _b(w, "sample.csv", _write_csv),
    "tsv": lambda w: _b(w, "sample.tsv", _write_tsv),
    "psv": lambda w: _b(w, "sample.psv", _write_psv),
    "semicolon_csv": lambda w: _b(w, "eu.csv", lambda p: _write_csv(p, delimiter=";")),
    "pipe_txt": lambda w: _b(w, "pipe.txt", _write_psv),
    "tab_txt": lambda w: _b(w, "tab.txt", _write_tsv),
    "dat_csv": lambda w: _b(w, "export.dat", _write_csv),
    "csv_single_col": lambda w: _b(w, "ids.csv", lambda p: p.write_text("id\n1\n2\n3\n", encoding="utf-8")),
    "csv_wide": lambda w: _b(w, "wide.csv", lambda p: p.write_text(
        "c1,c2,c3,c4,c5\n" + "\n".join(f"{i},{i},{i},{i},{i}" for i in range(10)) + "\n", encoding="utf-8"
    )),
    # --- fixed-width ---
    "fixed_width_dat": lambda w: _b(w, "payroll.dat", _write_fixed_width),
    "fixed_width_txt": lambda w: _b(w, "payroll.txt", _write_fixed_width),
    "fixed_width_fw": lambda w: _b(w, "ledger.fw", _write_fixed_width),
    "fixed_width_fixed_ext": lambda w: _b(w, "records.fixed", _write_fixed_width),
    # --- json ---
    "json_object": lambda w: _b(w, "doc.json", _write_json_object),
    "json_array": lambda w: _b(w, "arr.json", _write_json_array),
    "jsonl": lambda w: _b(w, "stream.ndjson", _write_jsonl),
    "json_pretty": lambda w: _b(w, "pretty.json", lambda p: p.write_text(
        json.dumps({"users": [{"id": 1, "name": "alice"}]}, indent=2), encoding="utf-8"
    )),
    "json_utf8_bom": lambda w: _b(w, "bom.json", lambda p: p.write_bytes(
        b"\xef\xbb\xbf" + json.dumps({"id": 1}).encode("utf-8")
    )),
    # --- markup ---
    "xml": lambda w: _b(w, "feed.xml", _write_xml),
    "yaml": lambda w: _b(w, "config.yaml", _write_yaml),
    "yml": lambda w: _b(w, "settings.yml", _write_yaml),
    "html": lambda w: _b(w, "page.html", _write_html),
    "svg": lambda w: _b(w, "icon.svg", _write_svg),
    "markdown": lambda w: _b(w, "readme.md", lambda p: p.write_text("# Title\n\nParagraph text.\n", encoding="utf-8")),
    # --- columnar ---
    "parquet": lambda w: _b(w, "table.parquet", _write_parquet),
    "parquet_pq": lambda w: _b(w, "table.pq", _write_parquet),
    "orc": lambda w: _b(w, "table.orc", _write_orc),
    "avro": lambda w: _b(w, "events.avro", _write_avro),
    # --- images ---
    "png": lambda w: _b(w, "logo.png", _write_png),
    "jpeg": lambda w: _b(w, "photo.jpg", _write_jpeg),
    "jpeg_ext": lambda w: _b(w, "photo.jpeg", _write_jpeg),
    "gif": lambda w: _b(w, "anim.gif", _write_gif),
    "webp": lambda w: _b(w, "img.webp", _write_webp),
    "bmp": lambda w: _b(w, "img.bmp", _write_bmp),
    # --- documents ---
    "pdf": lambda w: _b(w, "doc.pdf", _write_pdf),
    # --- plain / empty ---
    "plain_txt": lambda w: _b(w, "notes.txt", _write_plain_text),
    "log_txt": lambda w: _b(w, "app.log", _write_log_text),
    "empty_txt": lambda w: _b(w, "empty.txt", lambda p: p.write_bytes(b"")),
    "empty_dat": lambda w: _b(w, "empty.dat", lambda p: p.write_bytes(b"")),
    "empty_csv": lambda w: _b(w, "empty.csv", lambda p: p.write_bytes(b"")),
    "unstructured_dat": lambda w: _b(w, "blob.dat", _write_plain_text),
    # --- binary other ---
    "binary_blob": lambda w: _b(w, "unknown.bin", _write_binary_blob),
    "sqlite": lambda w: _b(w, "data.sqlite", _write_sqlite),
    # --- zip inner ---
    "zip_csv": lambda w: _zip_member(w, "bundle.zip", "data.csv", _write_csv),
    "zip_tsv": lambda w: _zip_member(w, "bundle.zip", "data.tsv", _write_tsv),
    "zip_psv": lambda w: _zip_member(w, "bundle.zip", "data.psv", _write_psv),
    "zip_json": lambda w: _zip_member(w, "bundle.zip", "data.json", _write_json_object),
    "zip_parquet": lambda w: _zip_member(w, "bundle.zip", "data.parquet", _write_parquet),
    "zip_orc": lambda w: _zip_member(w, "bundle.zip", "data.orc", _write_orc),
    "zip_avro": lambda w: _zip_member(w, "bundle.zip", "data.avro", _write_avro),
    "zip_png": lambda w: _zip_member(w, "bundle.zip", "logo.png", _write_png),
    "zip_pdf": lambda w: _zip_member(w, "bundle.zip", "doc.pdf", _write_pdf),
    "zip_xml": lambda w: _zip_member(w, "bundle.zip", "feed.xml", _write_xml),
    "zip_fixed_width_txt": lambda w: _zip_member(w, "bundle.zip", "payroll.txt", _write_fixed_width),
    "zip_delimited_txt": lambda w: _zip_member(w, "bundle.zip", "data.txt", _write_csv),
    "zip_plain_txt": lambda w: _zip_member(w, "bundle.zip", "notes.txt", _write_plain_text),
    "zip_zip_csv": lambda w: _nested_zip_csv(w, 2),
    "zip_zip_zip_csv": lambda w: _nested_zip_csv(w, 3),
    # --- tar inner ---
    "tar_csv": lambda w: _tar_member(w, "bundle.tar", "rows.csv", _write_csv),
    "tar_tsv": lambda w: _tar_member(w, "bundle.tar", "rows.tsv", _write_tsv),
    "tar_json": lambda w: _tar_member(w, "bundle.tar", "doc.json", _write_json_object),
    "tar_parquet": lambda w: _tar_member(w, "bundle.tar", "table.parquet", _write_parquet),
    "tar_fixed_width_txt": lambda w: _tar_member(w, "bundle.tar", "payroll.txt", _write_fixed_width),
    "tar_gz_csv": lambda w: _tar_gz_csv(w),
    "tgz_csv": lambda w: _tar_gz_csv(w, name="bundle.tgz"),
    # --- compression ---
    "gzip_csv": lambda w: _gzip_file(w, "data.csv.gz", b"id,name\n1,alice\n2,bob\n"),
    "gzip_json": lambda w: _gzip_file(w, "doc.json.gz", b'{"id":1,"name":"alice"}\n'),
    "gzip_fixed_width_txt": lambda w: _gzip_file(
        w, "payroll.txt.gz", (
            "ID      NAME                AMOUNT\n"
            "00000001ALICE SMITH          00001234\n"
            "00000002BOB JONES            00005678\n"
        ).encode("utf-8"),
    ),
    "bz2_csv": lambda w: _bz2_file(w, "data.csv.bz2", b"a,b,c\n1,2,3\n4,5,6\n"),
    # --- filename-only fallback (non-openable archive stub) ---
    "name_csv_zip": lambda w: _write_zip_stub(w, "report.csv.zip"),
    "name_json_gz": lambda w: _write_gzip_stub(w, "export.json.gz"),
    "name_fw_txt_zip": lambda w: _write_zip_stub(w, "payroll.txt.zip"),
    # --- extra coverage ---
    "json_in_zip_nested": lambda w: _nested_zip_member(w, "outer.zip", "data.json", _write_json_object),
    "csv_no_header": lambda w: _b(w, "noheader.csv", lambda p: p.write_text("1,alice,90\n2,bob,85\n", encoding="utf-8")),
    "tsv_no_header": lambda w: _b(w, "noheader.tsv", lambda p: p.write_text("1\talice\t90\n2\tbob\t85\n", encoding="utf-8")),
    "fixed_width_no_header": lambda w: _b(w, "rows.dat", lambda p: p.write_text(
        "00000001ALICE SMITH          00001234\n00000002BOB JONES            00005678\n", encoding="utf-8"
    )),
    "json_array_pretty": lambda w: _b(w, "users.json", lambda p: p.write_text(
        json.dumps([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}], indent=2), encoding="utf-8"
    )),
    "zip_yaml": lambda w: _zip_member(w, "config.zip", "app.yaml", _write_yaml),
    "tar_xml": lambda w: _tar_member(w, "feed.tar", "catalog.xml", _write_xml),
    "tar_png": lambda w: _tar_member(w, "assets.tar", "logo.png", _write_png),
    "zip_jsonl": lambda w: _zip_member(w, "events.zip", "stream.ndjson", _write_jsonl),
    "gzip_tsv": lambda w: _gzip_file(w, "data.tsv.gz", b"id\tname\n1\talice\n"),
    "log_file": lambda w: _b(w, "app.log", _write_log_text),
    # --- misleading extensions (content != suffix) ---
    "csv_abc": lambda w: _b(w, "data.abc", _write_csv),
    "fixed_verizon": lambda w: _b(w, "payroll.verizon", _write_fixed_width),
    "json_xyz": lambda w: _b(w, "payload.xyz", _write_json_object),
    "parquet_warehouse": lambda w: _b(w, "table.warehouse", _write_parquet),
    "tsv_acme": lambda w: _b(w, "report.acme", _write_tsv),
    "gzip_tar_csv_ext": lambda w: _gzip_tar_csv_multiext(w, "export.csv.gz.tar"),
    "zip_gzip_csv_wrong": lambda w: _zip_gzip_csv_wrong_ext(w),
    "zip_gzip_tar_csv_quad": lambda w: _zip_gzip_tar_csv_quad(w),
    "zip_fw_abc": lambda w: _zip_member(w, "package.zip", "payroll.abc", _write_fixed_width),
    "zip_csv_acme": lambda w: _zip_member(w, "bundle.acme", "data.abc", _write_csv),
    "bz2_csv_acme": lambda w: _bz2_file(w, "snapshot.acme", b"id,name\n1,alice\n"),
    "name_gzip_tar_csv": lambda w: _write_gzip_stub(w, "export.csv.gz.tar"),
    "name_quad_ext": lambda w: _write_zip_stub(w, "report.csv.gz.zip.verizon"),
}


def _gzip_tar_csv_multiext(work: Path, name: str) -> Path:
    inner = work / "inner.csv"
    _write_csv(inner)
    tar_path = work / "temp.tar"
    with tarfile.open(tar_path, "w") as tf:
        tf.add(inner, arcname="data.csv")
    out = work / name
    with tar_path.open("rb") as src, gzip.open(out, "wb") as dst:
        dst.write(src.read())
    return out


def _zip_gzip_csv_wrong_ext(work: Path) -> Path:
    gz_path = work / "d.csv.gz"
    with gzip.open(gz_path, "wb") as fh:
        fh.write(b"id,name\n1,alice\n")
    archive = work / "archive.verizon.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(gz_path, arcname="d.csv.gz")
    return archive


def _zip_gzip_tar_csv_quad(work: Path) -> Path:
    csv_path = work / "rows.csv"
    _write_csv(csv_path)
    tar_path = work / "layer.tar"
    with tarfile.open(tar_path, "w") as tf:
        tf.add(csv_path, arcname="rows.csv")
    tgz_path = work / "layer.tar.gz"
    with tar_path.open("rb") as src, gzip.open(tgz_path, "wb") as dst:
        dst.write(src.read())
    archive = work / "quad.custom"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.write(tgz_path, arcname="layer.tar.gz")
    return archive


def _nested_zip_member(
    work: Path, archive_name: str, member_name: str, writer: Callable[[Path], None]
) -> Path:
    inner = work / "payload"
    writer(inner)
    mid = work / "mid.zip"
    with zipfile.ZipFile(mid, "w") as zf:
        zf.write(inner, arcname=member_name)
    outer = work / archive_name
    with zipfile.ZipFile(outer, "w") as zf:
        zf.write(mid, arcname="mid.zip")
    return outer


def _tar_gz_csv(work: Path, name: str = "bundle.tar.gz") -> Path:
    inner = work / "inner.csv"
    _write_csv(inner)
    tar_path = work / "temp.tar"
    with tarfile.open(tar_path, "w") as tf:
        tf.add(inner, arcname="rows.csv")
    out = work / name
    with tar_path.open("rb") as src, gzip.open(out, "wb") as dst:
        dst.write(src.read())
    return out


def _write_zip_stub(work: Path, name: str) -> Path:
    path = work / name
    path.write_bytes(b"PK\x03\x04" + b"\x00" * 48)
    return path


def _write_gzip_stub(work: Path, name: str) -> Path:
    path = work / name
    path.write_bytes(b"\x1f\x8b\x08\x00" + b"\x00" * 16)
    return path


def build_case(work: Path, case: AccuracyCase) -> Path:
    fn = BUILDERS.get(case.builder)
    if fn is None:
        raise ValueError(f"unknown builder {case.builder!r}")
    return fn(work)


def _case(name: str, label: str, builder: str, fmt: str | None = None, category: str = "other") -> AccuracyCase:
    return AccuracyCase(name=name, expected_label=label, expected_format=fmt, builder=builder, category=category)


ACCURACY_CASES: tuple[AccuracyCase, ...] = (
    # Delimited (10)
    _case("csv", "csv", "csv", "csv", "delimited"),
    _case("tsv", "tsv", "tsv", "tsv", "delimited"),
    _case("psv", "psv", "psv", "psv", "delimited"),
    _case("semicolon csv", "csv", "semicolon_csv", "csv", "delimited"),
    _case("pipe-delimited .txt", "psv", "pipe_txt", "psv", "delimited"),
    _case("tab-delimited .txt", "tsv", "tab_txt", "tsv", "delimited"),
    _case("comma-delimited .dat", "dat", "dat_csv", "csv", "delimited"),
    _case("csv single column", "csv", "csv_single_col", "csv", "delimited"),
    _case("csv wide", "csv", "csv_wide", "csv", "delimited"),
    # Fixed-width (4)
    _case("fixed-width .dat", "fixed-width", "fixed_width_dat", "fixed-width", "fixed-width"),
    _case("fixed-width .txt", "fixed-width", "fixed_width_txt", "fixed-width", "fixed-width"),
    _case("fixed-width .fw", "fixed-width", "fixed_width_fw", "fixed-width", "fixed-width"),
    _case("fixed-width .fixed", "fixed-width", "fixed_width_fixed_ext", "fixed-width", "fixed-width"),
    # JSON (5)
    _case("json object", "json", "json_object", "json", "json"),
    _case("json array", "json", "json_array", "json", "json"),
    _case("jsonl / ndjson", "json", "jsonl", "json", "json"),
    _case("json pretty-printed", "json", "json_pretty", "json", "json"),
    _case("json utf-8 bom", "json", "json_utf8_bom", "json", "json"),
    # Markup (6)
    _case("xml", "xml", "xml", None, "markup"),
    _case("yaml", "yaml", "yaml", None, "markup"),
    _case("yml", "yaml", "yml", None, "markup"),
    _case("html", "xml", "html", None, "markup"),
    _case("svg", "xml", "svg", None, "markup"),
    _case("markdown", "txt", "markdown", None, "markup"),
    # Columnar (4)
    _case("parquet", "parquet", "parquet", "parquet", "columnar"),
    _case("parquet .pq", "parquet", "parquet_pq", "parquet", "columnar"),
    _case("orc", "orc", "orc", "orc", "columnar"),
    _case("avro", "avro", "avro", "avro", "columnar"),
    # Images (6)
    _case("png", "png", "png", None, "image"),
    _case("jpeg .jpg", "jpeg", "jpeg", None, "image"),
    _case("jpeg .jpeg", "jpeg", "jpeg_ext", None, "image"),
    _case("gif", "gif", "gif", None, "image"),
    _case("webp", "webp", "webp", None, "image"),
    _case("bmp", "bmp", "bmp", None, "image"),
    # Documents (1)
    _case("pdf", "pdf", "pdf", None, "document"),
    # Plain / empty (6)
    _case("plain .txt", "txt", "plain_txt", None, "plain"),
    _case("log .txt", "txt", "log_txt", None, "plain"),
    _case("empty .txt", "empty", "empty_txt", None, "plain"),
    _case("empty .dat", "empty", "empty_dat", None, "plain"),
    _case("empty .csv", "empty", "empty_csv", None, "plain"),
    _case("unstructured .dat", "txt", "unstructured_dat", None, "plain"),
    # Binary (2)
    _case("binary blob", "bin", "binary_blob", None, "binary"),
    _case("sqlite", "sqlite", "sqlite", None, "binary"),
    # Zip archives (13)
    _case("zip -> csv", "zip -> csv", "zip_csv", None, "archive"),
    _case("zip -> tsv", "zip -> tsv", "zip_tsv", None, "archive"),
    _case("zip -> psv", "zip -> psv", "zip_psv", None, "archive"),
    _case("zip -> json", "zip -> json", "zip_json", None, "archive"),
    _case("zip -> parquet", "zip -> parquet", "zip_parquet", None, "archive"),
    _case("zip -> orc", "zip -> orc", "zip_orc", None, "archive"),
    _case("zip -> avro", "zip -> avro", "zip_avro", None, "archive"),
    _case("zip -> png", "zip -> png", "zip_png", None, "archive"),
    _case("zip -> pdf", "zip -> pdf", "zip_pdf", None, "archive"),
    _case("zip -> xml", "zip -> xml", "zip_xml", None, "archive"),
    _case("zip -> fixed-width", "zip -> fixed-width", "zip_fixed_width_txt", None, "archive"),
    _case("zip -> delimited txt", "zip -> csv", "zip_delimited_txt", None, "archive"),
    _case("zip -> plain txt", "zip -> txt", "zip_plain_txt", None, "archive"),
    _case("zip -> zip -> csv", "zip -> zip -> csv", "zip_zip_csv", None, "archive"),
    _case("zip -> zip -> zip -> csv", "zip -> zip -> zip -> csv", "zip_zip_zip_csv", None, "archive"),
    # Tar archives (6)
    _case("tar -> csv", "tar -> csv", "tar_csv", None, "archive"),
    _case("tar -> tsv", "tar -> tsv", "tar_tsv", None, "archive"),
    _case("tar -> json", "tar -> json", "tar_json", None, "archive"),
    _case("tar -> parquet", "tar -> parquet", "tar_parquet", None, "archive"),
    _case("tar -> fixed-width", "tar -> fixed-width", "tar_fixed_width_txt", None, "archive"),
    _case("tar.gz -> csv", "gzip -> tar -> csv", "tar_gz_csv", None, "archive"),
    _case("tgz -> csv", "gzip -> tar -> csv", "tgz_csv", None, "archive"),
    # Compression (4)
    _case("gzip -> csv", "gzip -> csv", "gzip_csv", None, "compression"),
    _case("gzip -> json", "gzip -> json", "gzip_json", None, "compression"),
    _case("gzip -> fixed-width", "gzip -> fixed-width", "gzip_fixed_width_txt", None, "compression"),
    _case("bzip2 -> csv", "bzip2 -> csv", "bz2_csv", None, "compression"),
    _case("gzip -> tsv", "gzip -> tsv", "gzip_tsv", None, "compression"),
    # Extra coverage (10)
    _case("zip -> zip -> json", "zip -> zip -> json", "json_in_zip_nested", None, "archive"),
    _case("csv no header", "csv", "csv_no_header", "csv", "delimited"),
    _case("tsv no header", "tsv", "tsv_no_header", "tsv", "delimited"),
    _case("fixed-width no header", "fixed-width", "fixed_width_no_header", "fixed-width", "fixed-width"),
    _case("json array indented", "json", "json_array_pretty", "json", "json"),
    _case("zip -> yaml", "zip -> yaml", "zip_yaml", None, "archive"),
    _case("tar -> xml", "tar -> xml", "tar_xml", None, "archive"),
    _case("tar -> png", "tar -> png", "tar_png", None, "archive"),
    _case("zip -> jsonl", "zip -> json", "zip_jsonl", None, "archive"),
    _case("log file .log", "txt", "log_file", None, "plain"),
    # Filename fallback (3)
    _case("name: report.csv.zip", "zip -> csv", "name_csv_zip", None, "fallback"),
    _case("name: export.json.gz", "gzip -> json", "name_json_gz", None, "fallback"),
    _case("name: payroll.txt.zip", "zip -> txt", "name_fw_txt_zip", None, "fallback"),
    # Misleading extensions — content sniff must win (13)
    _case("csv content .abc", "csv", "csv_abc", "csv", "misleading-ext"),
    _case("fixed-width .verizon", "fixed-width", "fixed_verizon", "fixed-width", "misleading-ext"),
    _case("json content .xyz", "json", "json_xyz", "json", "misleading-ext"),
    _case("parquet content .warehouse", "parquet", "parquet_warehouse", "parquet", "misleading-ext"),
    _case("tsv content .acme", "tsv", "tsv_acme", "tsv", "misleading-ext"),
    _case("gzip -> tar -> csv (.csv.gz.tar)", "gzip -> tar -> csv", "gzip_tar_csv_ext", None, "misleading-ext"),
    _case("zip -> gzip -> csv (wrong ext)", "zip -> gzip -> csv", "zip_gzip_csv_wrong", None, "misleading-ext"),
    _case("zip -> gzip -> tar -> csv", "zip -> gzip -> tar -> csv", "zip_gzip_tar_csv_quad", None, "misleading-ext"),
    _case("zip -> fixed-width (.abc)", "zip -> fixed-width", "zip_fw_abc", None, "misleading-ext"),
    _case("zip -> csv (.abc member)", "zip -> csv", "zip_csv_acme", None, "misleading-ext"),
    _case("bzip2 -> csv (.acme)", "bzip2 -> csv", "bz2_csv_acme", None, "misleading-ext"),
    _case("name: export.csv.gz.tar", "gzip -> tar -> csv", "name_gzip_tar_csv", None, "misleading-ext"),
    _case("name: report.csv.gz.zip.verizon", "zip -> gzip -> csv", "name_quad_ext", None, "misleading-ext"),
)
