# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T14:52:27Z
# --- END GENERATED FILE METADATA ---

"""In-memory fixed-width source/target reconciliation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

import polars as pl

from pegasus.schemas.validation import FixedWidthConfig, FixedWidthField, FixedWidthMatchStrategy
from pegasus.validation.comparators.core import _lit, eq
from pegasus.validation.comparators.models import (
    MISMATCH_REPORT_SCHEMA,
    MismatchReport,
    MismatchType,
    VALUE_MISMATCH_ROWS_SUMMARY_KEY,
    empty_mismatch_frame,
)
from pegasus.validation.fixed_width_dates import dates_equal_fixed_width


def slice_field(line: str, start: int, end: int) -> str:
    return line[start:end].strip() if end > start else ""


def _iter_nonempty_lines(path: Path) -> Iterator[str]:
    with path.open(encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if line.strip():
                yield line


def _field_spec(
    field: FixedWidthField,
    *,
    side: str,
) -> tuple[int, int]:
    if side == "source":
        return field.source_start, field.source_end
    return field.target_start, field.target_end


def _record_from_line(
    line: str,
    fields: list[FixedWidthField],
    *,
    side: str,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in fields:
        start, end = _field_spec(field, side=side)
        out[field.field_name] = slice_field(line, start, end)
    return out


def read_fixed_width_records(
    path: Path,
    config: FixedWidthConfig,
    *,
    side: str,
) -> list[dict[str, str]]:
    fields = list(config.fields)
    if not fields:
        raise ValueError("fixed_width_config.fields must not be empty")
    return [_record_from_line(line, fields, side=side) for line in _iter_nonempty_lines(path)]


def _resolve_uid_field(config: FixedWidthConfig) -> FixedWidthField:
    uid_name = (config.uid_column or "").strip()
    for field in config.fields:
        if field.field_name == uid_name:
            return field
    if config.fields:
        return config.fields[0]
    raise ValueError("fixed_width_config has no fields")


def _apply_regex(value: str, pattern: str | None, replacement: str) -> str:
    if not pattern:
        return value
    try:
        return re.sub(pattern, replacement, value)
    except re.error:
        return value


def _transform_field_value(value: str, field: FixedWidthField, *, side: str) -> str:
    if side == "source":
        return _apply_regex(value, field.source_regex_pattern, field.source_regex_replacement or "")
    return _apply_regex(value, field.target_regex_pattern, field.target_regex_replacement or "")


def _mask_sensitive(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return value
    return "*" * len(stripped)


def _compare_fields(config: FixedWidthConfig) -> list[FixedWidthField]:
    uid_field = _resolve_uid_field(config)
    return [
        f
        for f in config.fields
        if f.field_name != uid_field.field_name and getattr(f, "compare_enabled", True)
    ]


def _scan_structured_fields(
    source_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    compare_fields: list[FixedWidthField],
    *,
    scan_rows: int = 100,
) -> set[str]:
    found: set[str] = set()
    for field in compare_fields:
        if (field.field_type or "text").strip().lower() == "structured":
            found.add(field.field_name)
    for field in compare_fields:
        if field.field_name in found:
            continue
        for row in (*source_rows[:scan_rows], *target_rows[:scan_rows]):
            if isinstance(_lit(row.get(field.field_name, "")), (list, dict, tuple)):
                found.add(field.field_name)
                break
    return found


def fields_equal(
    source_value: str,
    target_value: str,
    field: FixedWidthField,
    *,
    structured_fields: set[str] | None = None,
) -> bool:
    field_type = (field.field_type or "text").strip().lower()
    if field_type == "structured" or (structured_fields and field.field_name in structured_fields):
        return eq(
            source_value,
            target_value,
            order=field.structured_order_sensitive,
            complex_mode=True,
        )
    if field_type == "date":
        src_fmt = field.source_date_format or field.date_format
        tgt_fmt = field.target_date_format or field.date_format
        return dates_equal_fixed_width(
            source_value,
            target_value,
            source_date_format=src_fmt,
            target_date_format=tgt_fmt,
        )
    if field_type == "integer":
        try:
            return int(source_value.strip()) == int(target_value.strip())
        except ValueError:
            return False
    if field_type == "float":
        try:
            return float(source_value.strip()) == float(target_value.strip())
        except ValueError:
            return False
    return source_value.strip() == target_value.strip()


def validate_fixed_width_pair(
    source_path: Path,
    target_path: Path,
    config: FixedWidthConfig | dict[str, Any],
    *,
    match_per_column_limit: int = 10,
) -> MismatchReport:
    """Compare two fixed-width files and return a mismatch report."""
    if not isinstance(config, FixedWidthConfig):
        config = FixedWidthConfig.model_validate(config)

    source_path = source_path.resolve()
    target_path = target_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    if not target_path.is_file():
        raise FileNotFoundError(f"Target file not found: {target_path}")

    uid_field = _resolve_uid_field(config)
    compare_fields = _compare_fields(config)
    source_rows = read_fixed_width_records(source_path, config, side="source")
    target_rows = read_fixed_width_records(target_path, config, side="target")
    structured_fields = _scan_structured_fields(source_rows, target_rows, compare_fields)

    source_by_uid: dict[str, dict[str, str]] = {}
    for row in source_rows:
        uid = row.get(uid_field.field_name, "").strip()
        source_by_uid[uid] = row

    target_by_uid: dict[str, dict[str, str]] = {}
    for row in target_rows:
        uid = row.get(uid_field.field_name, "").strip()
        target_by_uid[uid] = row

    mismatch_rows: list[dict[str, Any]] = []
    value_mismatch_uids: set[str] = set()

    for uid, src_row in source_by_uid.items():
        if uid not in target_by_uid:
            mismatch_rows.append({
                "uid": uid,
                "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                "column_name": None,
                "source_value": None,
                "target_value": None,
                "row_detail": json.dumps({"source_record": src_row}, ensure_ascii=False),
            })
            continue
        tgt_row = target_by_uid[uid]
        row_had_mismatch = False
        for field in compare_fields:
            src_val = _transform_field_value(src_row.get(field.field_name, ""), field, side="source")
            tgt_val = _transform_field_value(tgt_row.get(field.field_name, ""), field, side="target")
            if not fields_equal(src_val, tgt_val, field, structured_fields=structured_fields):
                row_had_mismatch = True
                report_src = _mask_sensitive(src_val) if field.is_sensitive else src_val
                report_tgt = _mask_sensitive(tgt_val) if field.is_sensitive else tgt_val
                mismatch_rows.append({
                    "uid": uid,
                    "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                    "column_name": field.field_name,
                    "source_value": report_src,
                    "target_value": report_tgt,
                    "row_detail": json.dumps(
                        {"source_record": src_row, "target_record": tgt_row},
                        ensure_ascii=False,
                    ),
                })
        if row_had_mismatch:
            value_mismatch_uids.add(uid)

    for uid, tgt_row in target_by_uid.items():
        if uid not in source_by_uid:
            mismatch_rows.append({
                "uid": uid,
                "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                "column_name": None,
                "source_value": None,
                "target_value": None,
                "row_detail": json.dumps({"target_record": tgt_row}, ensure_ascii=False),
            })

    if mismatch_rows:
        frame = pl.DataFrame(mismatch_rows, schema=MISMATCH_REPORT_SCHEMA)
    else:
        from pegasus.validation.match_sample import build_match_sample_rows_from_uid_maps

        match_rows = build_match_sample_rows_from_uid_maps(
            source_by_uid=source_by_uid,
            target_by_uid=target_by_uid,
            compare_columns=[f.field_name for f in compare_fields],
            per_column_limit=match_per_column_limit,
            mask_sensitive={f.field_name: f.is_sensitive for f in compare_fields},
        )
        frame = (
            pl.DataFrame(match_rows, schema=MISMATCH_REPORT_SCHEMA)
            if match_rows
            else empty_mismatch_frame()
        )

    missing = sum(1 for r in mismatch_rows if r["mismatch_type"] == MismatchType.MISSING_IN_TARGET.value)
    extra = sum(1 for r in mismatch_rows if r["mismatch_type"] == MismatchType.EXTRA_IN_TARGET.value)
    value_cells = sum(1 for r in mismatch_rows if r["mismatch_type"] == MismatchType.VALUE_MISMATCH.value)

    summary = {
        MismatchType.MISSING_IN_TARGET.value: missing,
        MismatchType.EXTRA_IN_TARGET.value: extra,
        MismatchType.VALUE_MISMATCH.value: len(value_mismatch_uids) if value_mismatch_uids else value_cells,
        VALUE_MISMATCH_ROWS_SUMMARY_KEY: len(value_mismatch_uids),
    }
    return MismatchReport(mismatches=frame, summary=summary)
