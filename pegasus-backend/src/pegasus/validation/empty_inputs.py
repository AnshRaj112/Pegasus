# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T10:37:33Z
# --- END GENERATED FILE METADATA ---

"""Validation shortcuts when one or both inputs contain no data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from pegasus.schemas.validation import ColumnMapping
from pegasus.services.validation_results import ValidationRunResult
from pegasus.validation.adapters.file_delimited import FileDelimitedAdapter
from pegasus.validation.comparators.models import (
    MISMATCH_REPORT_SCHEMA,
    MismatchReport,
    MismatchType,
    VALUE_MISMATCH_ROWS_SUMMARY_KEY,
    empty_mismatch_frame,
)
from pegasus.validation.delimiter_resolve import resolve_delimiter_for_paths
from pegasus.validation.pipeline.fingerprint import parse_identity_columns


def file_has_no_content(path: Path) -> bool:
    """Return True when *path* is missing, zero bytes, or whitespace-only."""
    if not path.is_file():
        return True
    if path.stat().st_size == 0:
        return True
    with path.open("rb") as handle:
        while True:
            block = handle.read(64 * 1024)
            if not block:
                break
            if block.strip():
                return False
    return True


def _record_uid(record: dict[str, Any], identity_columns: list[str]) -> str:
    parts = ["" if record.get(col) is None else str(record.get(col)).strip() for col in identity_columns]
    return "|".join(parts)


def _collect_records(adapter: FileDelimitedAdapter) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for chunk in adapter.stream_records(10_000):
        rows.extend(chunk)
    return rows


def _resolve_compare_columns(
    schema_names: list[str],
    uid_column: str,
    column_mappings: list[ColumnMapping] | None,
) -> list[str]:
    from pegasus.services.validation_service import _resolve_compare_columns

    return _resolve_compare_columns(schema_names, uid_column, column_mappings)


def validate_delimited_degenerate_pair(
    *,
    source_path: Path,
    target_path: Path,
    uid_column: str,
    delimiter: str = "auto",
    column_mappings: list[ColumnMapping] | None = None,
    has_header: bool = True,
    header_leading_rows: int = 0,
) -> ValidationRunResult | None:
    """Return a validation result when one or both files have no content.

    Returns ``None`` when both files contain at least one non-blank line so the
    caller can run the normal reconciliation pipeline.
    """
    source_path = source_path.resolve()
    target_path = target_path.resolve()
    source_empty = file_has_no_content(source_path)
    target_empty = file_has_no_content(target_path)
    if not source_empty and not target_empty:
        return None

    empty_summary = {
        MismatchType.MISSING_IN_TARGET.value: 0,
        MismatchType.EXTRA_IN_TARGET.value: 0,
        MismatchType.VALUE_MISMATCH.value: 0,
        VALUE_MISMATCH_ROWS_SUMMARY_KEY: 0,
    }
    if source_empty and target_empty:
        return ValidationRunResult(
            report=MismatchReport(mismatches=empty_mismatch_frame(), summary=empty_summary),
            source_row_count=0,
            target_row_count=0,
            compared_column_count=0,
            compared_columns=[],
            test_mode="full",
        )

    populated_path = target_path if source_empty else source_path
    sep = (
        resolve_delimiter_for_paths(delimiter, target_path, None)
        if source_empty
        else resolve_delimiter_for_paths(delimiter, source_path, None)
    )
    adapter = FileDelimitedAdapter(
        populated_path,
        delimiter=sep,
        has_header=has_header,
        skip_rows=header_leading_rows,
    )
    schema_names = adapter.get_schema().column_names
    compare_columns = _resolve_compare_columns(schema_names, uid_column, column_mappings)
    identity_columns = parse_identity_columns(uid_column) or [uid_column.strip()]
    records = _collect_records(adapter)

    mismatch_rows: list[dict[str, Any]] = []
    mismatch_type = (
        MismatchType.EXTRA_IN_TARGET.value if source_empty else MismatchType.MISSING_IN_TARGET.value
    )
    for record in records:
        uid = _record_uid(record, identity_columns)
        payload = {"target_record": record} if source_empty else {"source_record": record}
        mismatch_rows.append({
            "uid": uid,
            "mismatch_type": mismatch_type,
            "column_name": None,
            "source_value": None,
            "target_value": None,
            "row_detail": json.dumps(payload, ensure_ascii=False),
        })

    if mismatch_rows:
        frame = pl.DataFrame(mismatch_rows, schema=MISMATCH_REPORT_SCHEMA)
    else:
        frame = empty_mismatch_frame()

    summary = dict(empty_summary)
    key = (
        MismatchType.EXTRA_IN_TARGET.value
        if source_empty
        else MismatchType.MISSING_IN_TARGET.value
    )
    summary[key] = len(mismatch_rows)

    source_count = 0 if source_empty else len(records)
    target_count = len(records) if source_empty else 0
    return ValidationRunResult(
        report=MismatchReport(mismatches=frame, summary=summary),
        source_row_count=source_count,
        target_row_count=target_count,
        compared_column_count=len(compare_columns),
        compared_columns=compare_columns,
        test_mode="full",
    )
