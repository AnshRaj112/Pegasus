# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:22:13Z
# --- END GENERATED FILE METADATA ---

"""In-memory reconciliation must export every mismatch row, not just capped samples."""

from __future__ import annotations

import polars as pl

from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.pipeline.in_memory import build_in_memory_mismatch_frame
from pegasus.validation.pipeline.result import PipelineResult
from pegasus.validation.services.validation_run import pipeline_result_to_run_result


def test_build_in_memory_mismatch_frame_exports_all_categories() -> None:
    identity = ["id"]
    compare = ["sku", "amount"]
    src = pl.DataFrame({
        "id": ["m1", "both"],
        "sku": ["A", "B"],
        "amount": ["1", "2"],
    })
    tgt = pl.DataFrame({
        "id": ["e1", "both"],
        "sku": ["A", "C"],
        "amount": ["1", "2"],
    })
    src_id_fp = src.with_columns(pl.lit(1).alias("_fp"))
    tgt_id_fp = tgt.with_columns(pl.lit(2).alias("_fp"))
    missing_df = src_id_fp.join(tgt_id_fp.select(identity), on=identity, how="anti")
    extra_df = tgt_id_fp.join(src_id_fp.select(identity), on=identity, how="anti")
    inner = src_id_fp.join(tgt_id_fp, on=identity, how="inner", suffix="_tgt")
    changed_df = inner.filter(pl.col("_fp") != pl.col("_fp_tgt"))

    frame = build_in_memory_mismatch_frame(
        missing_df=missing_df,
        extra_df=extra_df,
        changed_df=changed_df,
        src=src,
        tgt=tgt,
        identity_columns=identity,
        compare_columns=compare,
        src_physical=compare,
        tgt_physical=compare,
        enable_column_drilldown=True,
        pol=None,
    )

    assert frame.height == 3
    by_type = frame.group_by("mismatch_type").len().sort("mismatch_type")
    counts = {row[0]: row[1] for row in by_type.iter_rows()}
    assert counts[MismatchType.MISSING_IN_TARGET.value] == 1
    assert counts[MismatchType.EXTRA_IN_TARGET.value] == 1
    assert counts[MismatchType.VALUE_MISMATCH.value] == 1

    missing_row = frame.filter(
        pl.col("mismatch_type") == pl.lit(MismatchType.MISSING_IN_TARGET.value)
    ).row(0, named=True)
    assert "sku" in missing_row["row_detail"]


def test_pipeline_result_to_run_result_prefers_full_mismatches() -> None:
    full = pl.DataFrame({
        "uid": ["m1", "e1", "v1"],
        "mismatch_type": [
            MismatchType.MISSING_IN_TARGET.value,
            MismatchType.EXTRA_IN_TARGET.value,
            MismatchType.VALUE_MISMATCH.value,
        ],
        "column_name": [None, None, "sku"],
        "source_value": [None, None, "A"],
        "target_value": [None, None, "B"],
        "row_detail": ["{}", "{}", "{}"],
    })
    result = PipelineResult(
        missing_count=1,
        extra_count=1,
        changed_count=1,
        full_mismatches=full,
        compared_columns=["sku"],
    )
    run = pipeline_result_to_run_result(result)
    assert run.report.mismatches.height == 3
