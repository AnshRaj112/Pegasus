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
