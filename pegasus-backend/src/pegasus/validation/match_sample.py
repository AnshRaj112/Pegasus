# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-28T11:56:30Z
# --- END GENERATED FILE METADATA ---

"""Sample matching rows for snippet view when validation finds no errors."""

from __future__ import annotations

import json
from typing import Any

import polars as pl

from pegasus.validation.comparators.models import MismatchType, empty_mismatch_frame
from pegasus.validation.pipeline.fingerprint import canonical


def _row_detail_json(
    *,
    source_record: dict[str, Any] | None = None,
    target_record: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {}
    if source_record:
        payload["source_record"] = source_record
    if target_record:
        payload["target_record"] = target_record
    return json.dumps(payload, ensure_ascii=False) if payload else ""


def _record_payload(record_key: str, row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    record: dict[str, Any] = {"uid": record_key}
    for col in columns:
        if col in row:
            val = row.get(col)
            record[col] = "" if val is None else str(val)
    return record


def _target_record_payload(record_key: str, row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    record: dict[str, Any] = {"uid": record_key}
    for col in columns:
        tgt_key = f"{col}_tgt"
        val = row.get(tgt_key, row.get(col))
        record[col] = "" if val is None else str(val)
    return record


def _identity_key_from_row(row: dict[str, Any], columns: list[str]) -> str:
    return "|".join(canonical(row.get(c)) for c in columns)


def build_match_sample_rows_from_uid_maps(
    *,
    source_by_uid: dict[str, dict[str, str]],
    target_by_uid: dict[str, dict[str, str]],
    compare_columns: list[str],
    per_column_limit: int = 10,
    mask_sensitive: dict[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """Build value_match snippet rows from uid -> row maps (fixed-width and adapter lookups)."""
    if per_column_limit <= 0 or not compare_columns:
        return []

    masks = mask_sensitive or {}
    col_counts = {col: 0 for col in compare_columns}
    rows: list[dict[str, Any]] = []

    for uid in sorted(set(source_by_uid) & set(target_by_uid)):
        src_row = source_by_uid[uid]
        tgt_row = target_by_uid[uid]
        row_detail = _row_detail_json(
            source_record={"uid": uid, **{col: src_row.get(col, "") for col in compare_columns}},
            target_record={"uid": uid, **{col: tgt_row.get(col, "") for col in compare_columns}},
        )
        for col in compare_columns:
            if col_counts[col] >= per_column_limit:
                continue
            sv = canonical(src_row.get(col, ""), column=col)
            tv = canonical(tgt_row.get(col, ""), column=col)
            if sv != tv:
                continue
            col_counts[col] += 1
            cell = sv if not masks.get(col) else sv
            rows.append({
                "uid": uid,
                "mismatch_type": MismatchType.VALUE_MATCH.value,
                "column_name": col,
                "source_value": cell,
                "target_value": cell if not masks.get(col) else tv,
                "row_detail": row_detail,
            })
        if all(col_counts[col] >= per_column_limit for col in compare_columns):
            break

    return rows


def build_match_sample_frame(
    *,
    src: pl.DataFrame,
    tgt: pl.DataFrame,
    identity_columns: list[str],
    compare_columns: list[str],
    per_column_limit: int = 10,
    pol: Any = None,
) -> pl.DataFrame:
    """Sample up to *per_column_limit* matching rows per compared column."""
    if per_column_limit <= 0 or not compare_columns or src.is_empty() or tgt.is_empty():
        return empty_mismatch_frame()

    src_lookup = src.select(list(dict.fromkeys([*identity_columns, *compare_columns])))
    tgt_lookup = tgt.select(list(dict.fromkeys([*identity_columns, *compare_columns])))
    detail = (
        src_lookup.join(tgt_lookup, on=identity_columns, how="inner", suffix="_tgt")
    )
    if detail.is_empty():
        return empty_mismatch_frame()

    col_counts = {col: 0 for col in compare_columns}
    rows: list[dict[str, Any]] = []

    for row in detail.iter_rows(named=True):
        key = _identity_key_from_row(row, identity_columns)
        source_record = _record_payload(key, row, compare_columns)
        target_record = _target_record_payload(key, row, compare_columns)
        row_detail = _row_detail_json(source_record=source_record, target_record=target_record)

        for col in compare_columns:
            if col_counts[col] >= per_column_limit:
                continue
            if pol is not None and getattr(pol, "fields", None):
                src_part = pol.canonical_side_part(row, col, side="source")
                tgt_part = pol.canonical_side_part(
                    {**row, col: row.get(f"{col}_tgt", row.get(col))},
                    col,
                    side="target",
                )
            else:
                src_part = canonical(row.get(col), column=col)
                tgt_part = canonical(row.get(f"{col}_tgt", row.get(col)), column=col)
            if src_part != tgt_part:
                continue
            sv = str(src_part) if src_part is not None else ""
            tv = str(tgt_part) if tgt_part is not None else ""
            if pol is not None:
                sv = pol.mask_if_sensitive(col, sv)
                tv = pol.mask_if_sensitive(col, tv)
            col_counts[col] += 1
            rows.append({
                "uid": key,
                "mismatch_type": MismatchType.VALUE_MATCH.value,
                "column_name": col,
                "source_value": sv,
                "target_value": tv,
                "row_detail": row_detail,
            })

        if all(col_counts[col] >= per_column_limit for col in compare_columns):
            break

    return pl.DataFrame(rows, schema=empty_mismatch_frame().schema) if rows else empty_mismatch_frame()
