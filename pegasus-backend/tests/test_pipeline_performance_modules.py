# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T07:10:42Z
# --- END GENERATED FILE METADATA ---

"""Tests for binary spill format and fingerprinting."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pegasus.validation.pipeline.fingerprint import (
    canonical,
    identity_key,
    row_fingerprint_bytes,
    row_fingerprint_hex,
)
from pegasus.validation.pipeline.spill import (
    PartitionWriter,
    decode_record,
    encode_columnar_partition,
    encode_record,
    iter_partition,
)


def test_canonical_null_literals() -> None:
    assert canonical(None) == "__NULL__"
    assert canonical("  NA ") == "__NULL__"
    assert canonical("hello") == "hello"


def test_xxhash_fingerprint_deterministic() -> None:
    record = {"a": "1", "b": "2"}
    fp1 = row_fingerprint_hex(record, ["a", "b"], algorithm="xxhash64")
    fp2 = row_fingerprint_hex(record, ["a", "b"], algorithm="xxhash64")
    assert fp1 == fp2
    assert len(row_fingerprint_bytes(record, ["a", "b"])) == 8


def test_spill_roundtrip_without_payload() -> None:
    fp = row_fingerprint_bytes({"x": "1"}, ["x"])
    encoded = encode_record("key-1", fp)
    key, fp_out, payload = decode_record(encoded[4:])
    assert key == "key-1"
    assert fp_out == fp
    assert payload is None


def test_spill_writer_and_reader() -> None:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        writer = PartitionWriter(base, "source", store_payload=True, compare_columns=["v"])
        writer.write(3, "id1", b"\x01" * 8, {"v": "a", "extra": "ignored"})
        writer.close()
        records = list(iter_partition(base / "source" / "part_00003.bin", compare_columns=["v"]))
        assert len(records) == 1
        assert records[0][0] == "id1"
        assert records[0][2] == {"v": "a"}


def test_identity_key() -> None:
    record = {"id": " 42 ", "name": "x"}
    assert identity_key(record, ["id"]) == "42"


def test_arrow_ipc_spill_roundtrip() -> None:
    from pegasus.validation.pipeline.arrow_spill import encode_arrow_partition, read_arrow_partition

    block = encode_arrow_partition(["k1", "k2"], [100, 200])
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "part_00001.bin"
        path.write_bytes(block)
        frame = read_arrow_partition(path)
    assert frame is not None
    assert frame.height == 2
    assert frame["identity"].to_list() == ["k1", "k2"]


def test_stage_report_format() -> None:
    from pegasus.validation.pipeline.timing import (
        PipelineIoStats,
        PipelineTimings,
        build_stage_metrics,
        format_stage_report,
    )

    timings = PipelineTimings(
        source_read_seconds=1.0,
        source_partition_seconds=3.0,
        target_read_seconds=0.5,
        target_partition_seconds=2.5,
        partition_reconciliation_seconds=2.0,
        total_seconds=9.0,
        total_cpu_seconds=8.0,
        source_read_cpu_seconds=0.9,
        source_partition_cpu_seconds=2.5,
        target_read_cpu_seconds=0.4,
        target_partition_cpu_seconds=2.0,
        partition_reconciliation_cpu_seconds=1.8,
    )
    io = PipelineIoStats(
        source_input_bytes=100,
        target_input_bytes=80,
        source_spill_bytes=50,
        target_spill_bytes=40,
        reconcile_spill_bytes_read=90,
    )
    report = format_stage_report(build_stage_metrics(timings, io))
    assert "Read Source:" in report
    assert "Wall Time: 1.0000 s" in report
    assert "CPU Time: 0.9000 s" in report
    assert "Bytes Read: 100" in report
    assert "Partition Source:" in report
    assert "Wall Time: 2.0000 s" in report
    assert "Bytes Written: 50" in report
    assert "%" not in report


def test_columnar_spill_without_payload_skips_compare_columns() -> None:
    """Fingerprint-only CBL2 blocks must not treat the next block header as column data."""
    block1 = encode_columnar_partition(["k1"], [111])
    block2 = encode_columnar_partition(["k2"], [222])
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "part_00001.bin"
        path.write_bytes(block1 + block2)
        rows = list(iter_partition(path, compare_columns=["c1", "c2"]))
    assert len(rows) == 2
    assert rows[0] == ("k1", (111).to_bytes(8, "big"), None)
    assert rows[1] == ("k2", (222).to_bytes(8, "big"), None)


def test_columnar_spill_roundtrip() -> None:
    payload = encode_columnar_partition(
        ["k1", "k2"],
        [111, 222],
        col_lists=[["a", "b"], ["1", "2"]],
    )
    assert payload.startswith(b"CBL2")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "part_00001.bin"
        path.write_bytes(payload)
        rows = list(iter_partition(path, compare_columns=["c1", "c2"]))
    assert len(rows) == 2
    assert rows[0][0] == "k1"
    assert rows[1][2] == {"c1": "b", "c2": "2"}
