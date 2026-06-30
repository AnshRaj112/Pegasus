# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T11:41:59Z
# --- END GENERATED FILE METADATA ---

"""Hierarchical JSON document comparison for source/target validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from pegasus.validation.comparators.core import eq
from pegasus.validation.comparators.models import (
    MISMATCH_REPORT_SCHEMA,
    MismatchReport,
    MismatchType,
    VALUE_MISMATCH_ROWS_SUMMARY_KEY,
    empty_mismatch_frame,
)

PathSegment = str | int
JSON_DOCUMENT_UID = "document"


def _is_complex(value: Any) -> bool:
    return isinstance(value, (dict, list, tuple))


def _path_str(segments: list[PathSegment]) -> str:
    if not segments:
        return "$"
    out = ""
    for seg in segments:
        if isinstance(seg, int):
            out += f"[{seg}]"
        elif out:
            out += f".{seg}"
        else:
            out = str(seg)
    return out or "$"


def _resolve_path(root: Any, segments: list[PathSegment]) -> Any:
    cur = root
    for seg in segments:
        if isinstance(seg, int):
            if not isinstance(cur, list) or seg < 0 or seg >= len(cur):
                return None
            cur = cur[seg]
        else:
            if not isinstance(cur, dict) or seg not in cur:
                return None
            cur = cur[seg]
    return cur


def _parent_segments(segments: list[PathSegment]) -> list[PathSegment]:
    return segments[:-1] if segments else []


def _siblings(root: Any, segments: list[PathSegment]) -> tuple[list[Any], list[Any]]:
    """Return (sibling_keys_or_indices, sibling_values) for the node at *segments*."""
    if not segments:
        return [], []
    parent = _resolve_path(root, _parent_segments(segments))
    leaf = segments[-1]
    if isinstance(parent, dict):
        keys = list(parent.keys())
        return keys, [parent[k] for k in keys]
    if isinstance(parent, list):
        return list(range(len(parent))), list(parent)
    return [], []


def _row_detail(
    *,
    json_path: str,
    parent_path: str,
    source_root: Any,
    target_root: Any,
    segments: list[PathSegment],
    mismatch_type: str,
    source_value: Any = None,
    target_value: Any = None,
) -> str:
    parent_segs = _parent_segments(segments)
    src_parent = _resolve_path(source_root, parent_segs) if parent_segs else source_root
    tgt_parent = _resolve_path(target_root, parent_segs) if parent_segs else target_root
    src_keys, src_siblings = _siblings(source_root, segments)
    tgt_keys, tgt_siblings = _siblings(target_root, segments)
    payload: dict[str, Any] = {
        "json_path": json_path,
        "parent_path": parent_path,
        "mismatch_type": mismatch_type,
    }
    if src_parent is not None:
        payload["source_parent"] = src_parent
    if tgt_parent is not None:
        payload["target_parent"] = tgt_parent
    if src_siblings:
        payload["source_sibling_keys"] = src_keys
        payload["source_siblings"] = src_siblings
    if tgt_siblings:
        payload["target_sibling_keys"] = tgt_keys
        payload["target_siblings"] = tgt_siblings
    if source_value is not None:
        payload["source_value"] = source_value
    if target_value is not None:
        payload["target_value"] = target_value
    return json.dumps(payload, ensure_ascii=False, default=str)


def _serialize_leaf(value: Any) -> str:
    if value is None:
        return "__NULL__"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)


def _append_mismatch(
    rows: list[dict[str, Any]],
    *,
    uid: str,
    segments: list[PathSegment],
    mismatch_type: str,
    source_root: Any,
    target_root: Any,
    source_value: Any = None,
    target_value: Any = None,
    column_name: str | None = None,
) -> None:
    json_path = _path_str(segments)
    parent_path = _path_str(_parent_segments(segments))
    rows.append({
        "uid": uid,
        "mismatch_type": mismatch_type,
        "column_name": column_name or json_path,
        "source_value": _serialize_leaf(source_value) if source_value is not None else None,
        "target_value": _serialize_leaf(target_value) if target_value is not None else None,
        "row_detail": _row_detail(
            json_path=json_path,
            parent_path=parent_path,
            source_root=source_root,
            target_root=target_root,
            segments=segments,
            mismatch_type=mismatch_type,
            source_value=source_value,
            target_value=target_value,
        ),
    })


def _diff_values(
    src: Any,
    tgt: Any,
    segments: list[PathSegment],
    *,
    uid: str,
    order_sensitive: bool,
    source_root: Any,
    target_root: Any,
    rows: list[dict[str, Any]],
) -> None:
    if eq(src, tgt, order=order_sensitive, complex_mode=True):
        return

    if isinstance(src, dict) and isinstance(tgt, dict):
        src_keys = list(src.keys()) if order_sensitive else sorted(src.keys(), key=str)
        for key in src_keys:
            child = segments + [key]
            if key not in tgt:
                _append_mismatch(
                    rows,
                    uid=uid,
                    segments=child,
                    mismatch_type=MismatchType.MISSING_IN_TARGET.value,
                    source_root=source_root,
                    target_root=target_root,
                    source_value=src[key],
                )
            else:
                _diff_values(
                    src[key],
                    tgt[key],
                    child,
                    uid=uid,
                    order_sensitive=order_sensitive,
                    source_root=source_root,
                    target_root=target_root,
                    rows=rows,
                )
        tgt_keys = list(tgt.keys()) if order_sensitive else sorted(tgt.keys(), key=str)
        for key in tgt_keys:
            if key not in src:
                _append_mismatch(
                    rows,
                    uid=uid,
                    segments=segments + [key],
                    mismatch_type=MismatchType.EXTRA_IN_TARGET.value,
                    source_root=source_root,
                    target_root=target_root,
                    target_value=tgt[key],
                )
        return

    if isinstance(src, list) and isinstance(tgt, list):
        if order_sensitive:
            max_len = max(len(src), len(tgt))
            for idx in range(max_len):
                child = segments + [idx]
                if idx >= len(src):
                    _append_mismatch(
                        rows,
                        uid=uid,
                        segments=child,
                        mismatch_type=MismatchType.EXTRA_IN_TARGET.value,
                        source_root=source_root,
                        target_root=target_root,
                        target_value=tgt[idx],
                    )
                elif idx >= len(tgt):
                    _append_mismatch(
                        rows,
                        uid=uid,
                        segments=child,
                        mismatch_type=MismatchType.MISSING_IN_TARGET.value,
                        source_root=source_root,
                        target_root=target_root,
                        source_value=src[idx],
                    )
                else:
                    _diff_values(
                        src[idx],
                        tgt[idx],
                        child,
                        uid=uid,
                        order_sensitive=order_sensitive,
                        source_root=source_root,
                        target_root=target_root,
                        rows=rows,
                    )
            return

        used_tgt: set[int] = set()
        for s_idx, s_item in enumerate(src):
            match_idx = None
            for t_idx, t_item in enumerate(tgt):
                if t_idx in used_tgt:
                    continue
                if eq(s_item, t_item, order=False, complex_mode=True):
                    match_idx = t_idx
                    break
            if match_idx is None:
                _append_mismatch(
                    rows,
                    uid=uid,
                    segments=segments + [s_idx],
                    mismatch_type=MismatchType.MISSING_IN_TARGET.value,
                    source_root=source_root,
                    target_root=target_root,
                    source_value=s_item,
                )
            else:
                used_tgt.add(match_idx)
                _diff_values(
                    s_item,
                    tgt[match_idx],
                    segments + [s_idx],
                    uid=uid,
                    order_sensitive=False,
                    source_root=source_root,
                    target_root=target_root,
                    rows=rows,
                )
        for t_idx, t_item in enumerate(tgt):
            if t_idx not in used_tgt:
                _append_mismatch(
                    rows,
                    uid=uid,
                    segments=segments + [t_idx],
                    mismatch_type=MismatchType.EXTRA_IN_TARGET.value,
                    source_root=source_root,
                    target_root=target_root,
                    target_value=t_item,
                )
        return

    _append_mismatch(
        rows,
        uid=uid,
        segments=segments,
        mismatch_type=MismatchType.VALUE_MISMATCH.value,
        source_root=source_root,
        target_root=target_root,
        source_value=src,
        target_value=tgt,
    )


def load_json_payload(path: Path) -> tuple[str, Any | list[dict[str, Any]]]:
    """Return ('document', root) for a single JSON file or ('ndjson', rows) for JSONL."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"JSON file is empty: {path}")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        rows: list[dict[str, Any]] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} of {path}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"NDJSON line {line_no} in {path} must be a JSON object")
            rows.append(row)
        if not rows:
            raise ValueError(f"JSON file has no records: {path}")
        return "ndjson", rows
    return "document", parsed


def _uid_from_record(record: dict[str, Any], uid_column: str) -> str:
    key = (uid_column or JSON_DOCUMENT_UID).strip() or JSON_DOCUMENT_UID
    if key == JSON_DOCUMENT_UID:
        return JSON_DOCUMENT_UID
    if key not in record:
        raise ValueError(f"UID field {key!r} not found in JSON record")
    return str(record[key])


def compare_json_documents(
    source: Any,
    target: Any,
    *,
    uid: str,
    order_sensitive: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _diff_values(
        source,
        target,
        [],
        uid=uid,
        order_sensitive=order_sensitive,
        source_root=source,
        target_root=target,
        rows=rows,
    )
    return rows


def validate_json_pair(
    source_path: Path,
    target_path: Path,
    *,
    uid_column: str = JSON_DOCUMENT_UID,
    order_sensitive: bool = False,
    match_per_column_limit: int = 10,
    parent_mappings: list[dict[str, Any]] | list[Any] | None = None,
) -> MismatchReport:
    """Compare two JSON files and return a mismatch report."""
    from pegasus.validation.json_parent_preview import (
        align_roots_with_parent_mappings,
        parent_mappings_from_column_mappings,
    )

    source_path = source_path.resolve()
    target_path = target_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    if not target_path.is_file():
        raise FileNotFoundError(f"Target file not found: {target_path}")

    src_mode, src_payload = load_json_payload(source_path)
    tgt_mode, tgt_payload = load_json_payload(target_path)
    if src_mode != tgt_mode:
        raise ValueError("Source and target must both be single JSON documents or both be NDJSON")

    parent_pairs = parent_mappings_from_column_mappings(parent_mappings)
    mismatch_rows: list[dict[str, Any]] = []
    value_mismatch_uids: set[str] = set()

    if src_mode == "document":
        uid = JSON_DOCUMENT_UID
        src_compare, tgt_compare = align_roots_with_parent_mappings(
            src_payload,
            tgt_payload,
            parent_pairs or None,
        )
        for row in compare_json_documents(
            src_compare,
            tgt_compare,
            uid=uid,
            order_sensitive=order_sensitive,
        ):
            mismatch_rows.append(row)
            if row["mismatch_type"] == MismatchType.VALUE_MISMATCH.value:
                value_mismatch_uids.add(uid)
        source_by_uid = {uid: {"document": json.dumps(src_payload, ensure_ascii=False)}}
        target_by_uid = {uid: {"document": json.dumps(tgt_payload, ensure_ascii=False)}}
        compared_columns = (
            [target for _, target in parent_pairs]
            if parent_pairs
            else ["document"]
        )
    else:
        source_by_uid = {_uid_from_record(r, uid_column): r for r in src_payload}
        target_by_uid = {_uid_from_record(r, uid_column): r for r in tgt_payload}
        compared_columns = sorted({
            key
            for rec in list(source_by_uid.values()) + list(target_by_uid.values())
            for key in rec.keys()
            if key != uid_column
        })
        if parent_pairs:
            compared_columns = sorted({target for _, target in parent_pairs})

        for uid, src_doc in source_by_uid.items():
            if uid not in target_by_uid:
                mismatch_rows.append({
                    "uid": uid,
                    "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": json.dumps({"source_record": src_doc}, ensure_ascii=False),
                })
                continue
            tgt_doc = target_by_uid[uid]
            src_compare, tgt_compare = align_roots_with_parent_mappings(
                src_doc,
                tgt_doc,
                parent_pairs or None,
            )
            row_had_value_mismatch = False
            for row in compare_json_documents(
                src_compare,
                tgt_compare,
                uid=uid,
                order_sensitive=order_sensitive,
            ):
                mismatch_rows.append(row)
                if row["mismatch_type"] == MismatchType.VALUE_MISMATCH.value:
                    row_had_value_mismatch = True
            if row_had_value_mismatch:
                value_mismatch_uids.add(uid)

        for uid, tgt_doc in target_by_uid.items():
            if uid not in source_by_uid:
                mismatch_rows.append({
                    "uid": uid,
                    "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                    "column_name": None,
                    "source_value": None,
                    "target_value": None,
                    "row_detail": json.dumps({"target_record": tgt_doc}, ensure_ascii=False),
                })

    if mismatch_rows:
        frame = pl.DataFrame(mismatch_rows, schema=MISMATCH_REPORT_SCHEMA)
    else:
        from pegasus.validation.match_sample import build_match_sample_rows_from_uid_maps

        match_rows = build_match_sample_rows_from_uid_maps(
            source_by_uid=source_by_uid,
            target_by_uid=target_by_uid,
            compare_columns=compared_columns,
            per_column_limit=match_per_column_limit,
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
