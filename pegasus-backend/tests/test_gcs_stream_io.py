# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T07:10:42Z
# --- END GENERATED FILE METADATA ---

"""GCS stream wrapper must satisfy TextIOWrapper (Python 3.12)."""

from __future__ import annotations

import io

from pegasus.validation.gcs_stream import _ReadAheadBinaryIO


def test_readahead_binary_io_text_wrapper() -> None:
    raw = io.BytesIO(b"a|1\nb|2\n")
    wrapped = _ReadAheadBinaryIO(raw)
    text = io.TextIOWrapper(wrapped, encoding="utf-8", errors="replace", newline="")
    assert text.readline().startswith("a")
    assert wrapped.writable() is False
