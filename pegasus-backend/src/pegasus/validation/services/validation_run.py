# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T10:54:18Z
# --- END GENERATED FILE METADATA ---

"""Convert pipeline results to ValidationRunResult."""

from __future__ import annotations

import polars as pl

from pegasus.services.validation_results import ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame
from pegasus.validation.pipeline.result import PipelineResult


def pipeline_result_to_run_result(result: PipelineResult) -> ValidationRunResult:
    rows: list[dict] = []
    for m in result.sample_mismatches:
        if m.mismatch_type == "missing":
            mtype = MismatchType.MISSING_IN_TARGET.value
        elif m.mismatch_type == "extra":
            mtype = MismatchType.EXTRA_IN_TARGET.value
        else:
            mtype = MismatchType.VALUE_MISMATCH.value

        if m.column_differences:
            for cd in m.column_differences:
                rows.append({
                    "uid": m.record_key,
                    "mismatch_type": mtype,
                    "column_name": cd.column,
                    "source_value": cd.source_value,
                    "target_value": cd.target_value,
                    "row_detail": "",
                })
        else:
            rows.append({
                "uid": m.record_key,
                "mismatch_type": mtype,
                "column_name": "",
                "source_value": "",
                "target_value": "",
                "row_detail": "",
            })

    frame = pl.DataFrame(rows) if rows else empty_mismatch_frame()
    summary = {
        MismatchType.MISSING_IN_TARGET.value: result.missing_count,
        MismatchType.EXTRA_IN_TARGET.value: result.extra_count,
        MismatchType.VALUE_MISMATCH.value: result.changed_count,
    }
    return ValidationRunResult(
        report=MismatchReport(mismatches=frame, summary=summary),
        source_row_count=result.source_row_count,
        target_row_count=result.target_row_count,
        compared_column_count=len(result.compared_columns),
        compared_columns=result.compared_columns,
        test_mode="full",
        pipeline_metadata={
            "schema_valid": result.schema_valid,
            "mismatched_partitions": result.mismatched_partitions,
            "execution_seconds": result.execution_seconds,
            "path": (result.extra_stats or {}).get("path"),
            "timings": (result.extra_stats or {}).get("timings"),
            "stages": (result.extra_stats or {}).get("stages"),
            "stage_report": (result.extra_stats or {}).get("stage_report"),
            "io": (result.extra_stats or {}).get("io"),
            "lazy_column_drilldown": (result.extra_stats or {}).get("lazy_column_drilldown"),
            "columnar_spill": (result.extra_stats or {}).get("columnar_spill"),
        },
    )
