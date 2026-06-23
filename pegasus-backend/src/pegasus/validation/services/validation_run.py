# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T05:59:19Z
# --- END GENERATED FILE METADATA ---

"""Convert pipeline results to ValidationRunResult."""

from __future__ import annotations

import json

import polars as pl

from pegasus.services.validation_results import ValidationRunResult
from pegasus.validation.comparators.models import MismatchReport, MismatchType, empty_mismatch_frame
from pegasus.validation.pipeline.result import ColumnDifference, PipelineResult


def _row_detail_json(
    *,
    source_record: dict | None = None,
    target_record: dict | None = None,
) -> str:
    payload: dict = {}
    if source_record:
        payload["source_record"] = source_record
    if target_record:
        payload["target_record"] = target_record
    return json.dumps(payload, ensure_ascii=False) if payload else ""


def _records_from_column_diffs(
    record_key: str,
    column_differences: list[ColumnDifference],
    compared_columns: list[str],
) -> tuple[dict, dict]:
    source_record: dict = {"uid": record_key}
    target_record: dict = {"uid": record_key}
    for col in compared_columns:
        source_record[col] = None
        target_record[col] = None
    for cd in column_differences:
        source_record[cd.column] = cd.source_value
        target_record[cd.column] = cd.target_value
    return source_record, target_record


def pipeline_result_to_run_result(result: PipelineResult) -> ValidationRunResult:
    if result.full_mismatches is not None and result.full_mismatches.height > 0:
        frame = result.full_mismatches
        value_row_count = int(
            frame.filter(pl.col("mismatch_type") == pl.lit(MismatchType.VALUE_MISMATCH.value)).height
        )
        summary = {
            MismatchType.MISSING_IN_TARGET.value: result.missing_count,
            MismatchType.EXTRA_IN_TARGET.value: result.extra_count,
            MismatchType.VALUE_MISMATCH.value: max(result.changed_count, value_row_count),
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
                "chunk_rows": (result.extra_stats or {}).get("chunk_rows"),
                "partition_buckets": (result.extra_stats or {}).get("partition_buckets"),
                "reconcile_workers": (result.extra_stats or {}).get("reconcile_workers"),
            },
        )

    rows: list[dict] = []
    for m in result.sample_mismatches:
        if m.mismatch_type == "missing":
            mtype = MismatchType.MISSING_IN_TARGET.value
        elif m.mismatch_type == "extra":
            mtype = MismatchType.EXTRA_IN_TARGET.value
        else:
            mtype = MismatchType.VALUE_MISMATCH.value

        if m.column_differences:
            source_record, target_record = _records_from_column_diffs(
                m.record_key,
                m.column_differences,
                result.compared_columns,
            )
            row_detail = _row_detail_json(
                source_record=source_record,
                target_record=target_record,
            )
            for cd in m.column_differences:
                rows.append({
                    "uid": m.record_key,
                    "mismatch_type": mtype,
                    "column_name": cd.column,
                    "source_value": cd.source_value,
                    "target_value": cd.target_value,
                    "row_detail": row_detail,
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
    value_row_count = 0
    for m in result.sample_mismatches:
        if m.mismatch_type != "changed":
            continue
        value_row_count += len(m.column_differences) or 1
    summary = {
        MismatchType.MISSING_IN_TARGET.value: result.missing_count,
        MismatchType.EXTRA_IN_TARGET.value: result.extra_count,
        MismatchType.VALUE_MISMATCH.value: max(result.changed_count, value_row_count),
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
            "chunk_rows": (result.extra_stats or {}).get("chunk_rows"),
            "partition_buckets": (result.extra_stats or {}).get("partition_buckets"),
            "reconcile_workers": (result.extra_stats or {}).get("reconcile_workers"),
        },
    )
