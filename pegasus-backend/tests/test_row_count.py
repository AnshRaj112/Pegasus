# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-11T00:00:00Z
# --- END GENERATED FILE METADATA ---

"""Delimited row counting."""

from __future__ import annotations

from pathlib import Path

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef
from pegasus.validation.gcs_stream import get_gcs_stream_session
from pegasus.validation.row_count import count_delimited_data_rows, count_physical_lines_stream


def test_count_generated_100k_source_rows(tmp_path: Path) -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-100k/source.csv")
    if not src.is_file():
        return

    adapter = FileDelimitedAdapter(src, delimiter="||", has_header=True)
    assert adapter.get_row_count() == 100_000
    assert count_delimited_data_rows(adapter) == 100_000


def test_count_physical_lines_without_trailing_newline(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    path.write_bytes(b"a\nb\nc")

    with path.open("rb") as handle:
        assert count_physical_lines_stream(handle) == 3

    adapter = FileDelimitedAdapter(path, delimiter=",", has_header=False)
    assert adapter.get_row_count() == 3


def test_gcs_adapter_row_count_uses_stream(tmp_path: Path) -> None:
    src = Path("/home/ansh.raj/Pegasus/test-data/generated-100k/source.csv")
    if not src.is_file():
        return

    ref = GcsObjectRef(
        bucket="demo-bucket",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "demo"},
    )
    adapter = GcsDelimitedAdapter(ref, delimiter="||", size_bytes=src.stat().st_size)
    get_gcs_stream_session(ref).store_cached_object_body(src.read_bytes())

    assert adapter.get_row_count() == 100_000
