# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-12T11:47:55Z
# --- END GENERATED FILE METADATA ---

"""GCS browse helpers — extension matching and object size metadata."""

from __future__ import annotations

from pegasus.validation.file_format import extensions_for_format, object_name_matches_format
from pegasus.validation.gcs_browse import _file_allowed, coerce_gcs_object_size


def test_object_name_matches_compressed_csv() -> None:
    allowed = extensions_for_format("csv")
    assert object_name_matches_format("exports/large.csv.gz", allowed)
    assert object_name_matches_format("data.csv", allowed)
    assert not object_name_matches_format("archive.zip", allowed)


def test_object_name_matches_extensionless_dump() -> None:
    allowed = extensions_for_format("csv")
    assert object_name_matches_format("warehouse_export_2026", allowed)


def test_file_allowed_delegates_to_object_name_matches_format() -> None:
    allowed = extensions_for_format("csv")
    assert _file_allowed("big_file.csv.gz", allowed)
    assert not _file_allowed("notes.pdf", allowed)


def test_coerce_gcs_object_size_accepts_large_values() -> None:
    over_500mb = 600 * 1024 * 1024
    assert coerce_gcs_object_size(over_500mb) == over_500mb
    assert coerce_gcs_object_size(str(over_500mb)) == over_500mb
    assert coerce_gcs_object_size(None) is None
    assert coerce_gcs_object_size("not-a-number") is None
