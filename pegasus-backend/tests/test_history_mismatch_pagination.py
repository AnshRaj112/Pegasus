# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T09:23:50Z
# --- END GENERATED FILE METADATA ---

"""Tests for packages mismatch pagination from NDJSON when totals were missing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pegasus.api.v1.mismatch_sample import paginate_mismatch_rows_from_ndjson


def test_paginate_ndjson_counts_file_when_totals_empty() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mismatches.ndjson"
        with path.open("w", encoding="utf-8") as fp:
            fp.write(json.dumps({"uid": "1", "mismatch_type": "value_mismatch", "column_name": "sku"}) + "\n")
            fp.write(json.dumps({"uid": "2", "mismatch_type": "missing_in_target"}) + "\n")

        items, total = paginate_mismatch_rows_from_ndjson(
            path,
            limit=10,
            offset=0,
            mismatch_type=None,
            totals_by_type=None,
        )
        assert total == 2
        assert len(items) == 2
