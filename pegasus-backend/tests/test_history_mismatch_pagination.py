# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T10:54:38Z
# --- END GENERATED FILE METADATA ---

"""Tests for packages mismatch pagination from NDJSON when totals were missing."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from pegasus.api.v1.mismatch_sample import paginate_mismatch_rows_from_ndjson


def test_paginate_ndjson_ignores_inflated_summary_totals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mismatches.ndjson"
        with path.open("w", encoding="utf-8") as fp:
            fp.write(json.dumps({"uid": "1", "mismatch_type": "value_mismatch", "column_name": "name"}) + "\n")

        inflated = {
            "missing_in_target": 0,
            "extra_in_target": 0,
            "value_mismatch": 1,
            "value_mismatch_rows": 1,
        }
        items, total = paginate_mismatch_rows_from_ndjson(
            path,
            limit=10,
            offset=0,
            mismatch_type=None,
            totals_by_type=inflated,
        )
        assert total == 1
        assert len(items) == 1


def test_paginate_ndjson_empty_file_returns_zero_total() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "mismatches.ndjson"
        path.write_text("", encoding="utf-8")
        items, total = paginate_mismatch_rows_from_ndjson(
            path,
            limit=10,
            offset=0,
            mismatch_type=None,
            totals_by_type={"missing_in_target": 2, "extra_in_target": 0, "value_mismatch": 1},
        )
        assert total == 0
        assert items == []


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


def test_run_result_from_job_dir_finds_mismatches_ndjson_without_result_paths() -> None:
    import json
    import uuid

    from pegasus.api.v1.validation_helpers import run_result_from_job_dir

    with tempfile.TemporaryDirectory() as tmp:
        job_dir = Path(tmp)
        run_id = uuid.uuid4()
        (job_dir / "meta.json").write_text(
            json.dumps({"run_id": str(run_id), "job_id": job_dir.name}),
            encoding="utf-8",
        )
        (job_dir / "result.json").write_text(
            json.dumps(
                {
                    "source_row_count": 2,
                    "target_row_count": 2,
                    "compared_column_count": 1,
                    "compared_columns": ["name"],
                    "summary": {
                        "missing_in_target": 0,
                        "extra_in_target": 0,
                        "value_mismatch": 1,
                        "value_mismatch_rows": 1,
                    },
                }
            ),
            encoding="utf-8",
        )
        with (job_dir / "mismatches.ndjson").open("w", encoding="utf-8") as fp:
            fp.write(
                json.dumps(
                    {
                        "uid": "1",
                        "mismatch_type": "value_mismatch",
                        "column_name": "name",
                        "source_value": "alice",
                        "target_value": "bob",
                    }
                )
                + "\n"
            )

        run_result, parsed_run_id, _meta = run_result_from_job_dir(job_dir)
        assert parsed_run_id == run_id
        assert run_result.report.mismatches.height == 1
        assert run_result.mismatch_artifact_path is not None
        assert run_result.mismatch_artifact_path.is_file()
