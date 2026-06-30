# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T06:20:06Z
# --- END GENERATED FILE METADATA ---

from __future__ import annotations

from pathlib import Path

from pegasus.validation.readers.multichar_csv import (
    can_use_fast_multichar_load,
    can_use_fast_multichar_load_bytes,
    load_multichar_csv_fast,
)

_REPO = Path("/home/ansh.raj/Pegasus")
_FIXTURE = _REPO / "test-data/generated-10k-8cols/source.csv"


def test_fast_multichar_load_matches_fixture_shape() -> None:
    if not _FIXTURE.is_file():
        return
    data = _FIXTURE.read_bytes()
    assert can_use_fast_multichar_load(_FIXTURE, "||")
    assert can_use_fast_multichar_load_bytes(data, "||")
    frame = load_multichar_csv_fast(_FIXTURE, delimiter="||", has_header=True, skip_rows=0)
    assert frame.height == 10_000
    assert "id" in frame.columns
