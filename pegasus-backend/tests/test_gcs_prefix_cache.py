# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T08:40:02Z
# --- END GENERATED FILE METADATA ---

"""GCS adapter prefix reads are cached across header and delimiter sampling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pegasus.validation.adapters.gcs_delimited import GcsDelimitedAdapter
from pegasus.validation.gcs_object import GcsObjectRef


def test_prefix_fetch_is_shared_between_header_and_sample() -> None:
    ref = GcsObjectRef(
        bucket="b",
        object_name="source.csv",
        credentials_info={"type": "service_account", "project_id": "p"},
    )
    adapter = GcsDelimitedAdapter(ref, delimiter=",", size_bytes=4096)
    session = MagicMock()
    session.read_prefix.return_value = b"id,name\n1,alice\n"

    with patch(
        "pegasus.validation.adapters.gcs_delimited.get_gcs_stream_session",
        return_value=session,
    ):
        header = adapter._load_header_prefix()
        sample = adapter._load_sample_prefix()

    assert header == sample
    session.read_prefix.assert_called_once()
