# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T11:22:54Z
# --- END GENERATED FILE METADATA ---

"""Match snippet samples when validation finds no errors."""

from __future__ import annotations

import polars as pl

from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.match_sample import (
    build_match_sample_frame,
    build_match_sample_rows_from_uid_maps,
)


def test_build_match_sample_rows_from_uid_maps_limits_per_column() -> None:
    source = {
        f"u{i}": {"id": f"u{i}", "amount": str(i), "status": "ok"}
        for i in range(20)
    }
    target = dict(source)
    rows = build_match_sample_rows_from_uid_maps(
        source_by_uid=source,
        target_by_uid=target,
        compare_columns=["amount", "status"],
        per_column_limit=10,
    )
    by_col: dict[str, int] = {}
    for row in rows:
        assert row["mismatch_type"] == MismatchType.VALUE_MATCH.value
        col = str(row["column_name"])
        by_col[col] = by_col.get(col, 0) + 1
    assert by_col.get("amount") == 10
    assert by_col.get("status") == 10


def test_build_match_sample_frame_polars() -> None:
    src = pl.DataFrame({
        "id": ["a", "b", "c"],
        "amount": ["1", "2", "3"],
    })
    tgt = pl.DataFrame({
        "id": ["a", "b", "c"],
        "amount": ["1", "2", "3"],
    })
    frame = build_match_sample_frame(
        src=src,
        tgt=tgt,
        identity_columns=["id"],
        compare_columns=["amount"],
        per_column_limit=10,
    )
    assert frame.height == 3
    assert frame["mismatch_type"].unique().to_list() == [MismatchType.VALUE_MATCH.value]
