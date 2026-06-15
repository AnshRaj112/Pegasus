# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-12T11:47:55Z
# --- END GENERATED FILE METADATA ---

from __future__ import annotations

import pytest

from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.pipeline.row_sanity import assert_reasonable_row_counts


def test_row_sanity_rejects_tiny_parse_of_large_file() -> None:
    src = FileDelimitedAdapter(
        "/home/ansh.raj/Pegasus/test-data/generated-100k/source.csv",
        delimiter="||",
    )
    tgt = FileDelimitedAdapter(
        "/home/ansh.raj/Pegasus/test-data/generated-100k/target.csv",
        delimiter="||",
    )
    if not src.path.is_file():
        pytest.skip("fixture missing")
    with pytest.raises(ValueError, match="parsed only 1 row"):
        assert_reasonable_row_counts(
            src,
            tgt,
            source_rows=1,
            target_rows=1,
            compare_column_count=3,
        )
