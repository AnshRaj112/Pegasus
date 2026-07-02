# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-01T10:19:19Z
# --- END GENERATED FILE METADATA ---

"""Tests for persisted footer / mismatch persistence parsing."""

from __future__ import annotations

from pegasus.schemas.validation import parse_stored_footer_blob


def test_parse_legacy_persistence_only_blob() -> None:
    footer, persistence = parse_stored_footer_blob(
        {
            "mismatch_rows_persisted": False,
            "mismatch_artifact_path": "/tmp/mismatches.ndjson",
            "mismatch_row_cap": 50000,
        }
    )
    assert footer is None
    assert persistence is not None
    assert persistence.mismatch_rows_persisted is False
    assert persistence.mismatch_artifact_path == "/tmp/mismatches.ndjson"
    assert persistence.mismatch_row_cap == 50000


def test_parse_nested_persistence_with_footer() -> None:
    footer, persistence = parse_stored_footer_blob(
        {
            "match": True,
            "enabled": True,
            "_persistence": {
                "mismatch_rows_persisted": False,
                "mismatch_artifact_path": "/tmp/mismatches.ndjson",
                "mismatch_row_cap": 50000,
            },
        }
    )
    assert footer is not None
    assert footer.match is True
    assert persistence is not None
    assert persistence.mismatch_row_cap == 50000
