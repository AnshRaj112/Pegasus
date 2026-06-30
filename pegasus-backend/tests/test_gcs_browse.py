# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T10:36:49Z
# --- END GENERATED FILE METADATA ---

"""GCS browse helpers — extension matching and object size metadata."""

from __future__ import annotations

from pegasus.validation.file_format import extensions_for_format, object_name_matches_format
from pegasus.validation.gcs_browse import (
    _blob_created_by,
    _blob_owner,
    _dt_iso,
    _entry_from_blob,
    _file_allowed,
    coerce_gcs_object_size,
)


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


def test_auto_format_includes_txt_and_dat() -> None:
    allowed = extensions_for_format("auto")
    assert object_name_matches_format("payroll.dat", allowed)
    assert object_name_matches_format("export.txt", allowed)
    assert object_name_matches_format("export.txt.gz", allowed)
    assert object_name_matches_format("data.csv", allowed)
    assert not _file_allowed("notes.pdf", allowed)


def test_any_format_alias_matches_auto() -> None:
    assert extensions_for_format("any") == extensions_for_format("auto")


def test_coerce_gcs_object_size_accepts_large_values() -> None:
    over_500mb = 600 * 1024 * 1024
    assert coerce_gcs_object_size(over_500mb) == over_500mb
    assert coerce_gcs_object_size(str(over_500mb)) == over_500mb
    assert coerce_gcs_object_size(None) is None
    assert coerce_gcs_object_size("not-a-number") is None


class _FakeBlob:
    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_entry_from_blob_maps_metadata_fields() -> None:
    from datetime import datetime, timezone

    created = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    updated = datetime(2026, 6, 7, 8, 9, 10, tzinfo=timezone.utc)
    blob = _FakeBlob(
        size=42,
        time_created=created,
        updated=updated,
        owner={"entity": "user-123@example.com"},
        metadata={"created_by": "etl-service"},
    )
    entry = _entry_from_blob(blob, path="data/file.csv", display_name="file.csv")
    assert entry.size_bytes == 42
    assert entry.created_at == created.isoformat()
    assert entry.updated_at == updated.isoformat()
    assert entry.owner == "123@example.com"
    assert entry.created_by == "etl-service"


def test_blob_owner_and_created_by_fallbacks() -> None:
    blob = _FakeBlob(metadata={"owner": "team-a", "creator": "alice"})
    assert _blob_owner(blob) == "team-a"
    assert _blob_created_by(blob) == "alice"
    assert _dt_iso(None) is None


def test_gcs_identity_strips_user_prefix() -> None:
    blob = _FakeBlob(
        owner={"entity": "user-deepak.k@onixnet.com"},
        metadata={"created_by": "user-deepak.k@onixnet.com"},
    )
    assert _blob_owner(blob) == "deepak.k@onixnet.com"
    assert _blob_created_by(blob) == "deepak.k@onixnet.com"
