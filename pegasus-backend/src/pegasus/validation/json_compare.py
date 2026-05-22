"""Canonical JSON document comparison (order-insensitive objects and arrays)."""

from __future__ import annotations

import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from pegasus.core.json_util import dumps_bytes, loads_bytes, loads_str
from pegasus.services.exceptions import ValidationBadRequestError


def _normalize_scalar(obj: Any) -> Any:
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float) and obj.is_integer():
        return int(obj)
    return obj


def canonical_json_value(obj: Any) -> Any:
    """Normalize *obj* so key order and list element order do not affect equality."""
    if isinstance(obj, dict):
        return {
            str(k): canonical_json_value(v)
            for k, v in sorted(obj.items(), key=lambda item: str(item[0]))
        }
    if isinstance(obj, list):
        normalized = [canonical_json_value(item) for item in obj]
        return sorted(normalized, key=dumps_bytes)
    return _normalize_scalar(obj)


def canonical_json_bytes(obj: Any) -> bytes:
    """Stable UTF-8 bytes for a canonical JSON value."""
    return dumps_bytes(canonical_json_value(obj))


def _list_multiset(left: list[Any], right: list[Any]) -> bool:
    left_counts = Counter(dumps_bytes(item) for item in left)
    right_counts = Counter(dumps_bytes(item) for item in right)
    return left_counts == right_counts


def json_values_equal(left: Any, right: Any) -> bool:
    """True when values match after canonicalization (sort_keys + multiset arrays)."""
    return _deep_equal(canonical_json_value(left), canonical_json_value(right))


def _deep_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return False
        return all(_deep_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return _list_multiset(left, right)
    return left == right


def describe_json_mismatch(left: Any, right: Any) -> dict[str, Any]:
    """Return a short summary of the first structural difference (for reports)."""
    left_c = canonical_json_value(left)
    right_c = canonical_json_value(right)
    path, detail = _first_diff(left_c, right_c, "$")
    src = canonical_json_bytes(left)
    tgt = canonical_json_bytes(right)
    offset = _first_byte_offset(src, tgt)
    return {
        "path": path,
        "detail": detail,
        "canonical_source_length": len(src),
        "canonical_target_length": len(tgt),
        "first_byte_offset": offset,
        "source_snippet": _snippet_at_offset(src, offset),
        "target_snippet": _snippet_at_offset(tgt, offset),
    }


def _first_byte_offset(left: bytes, right: bytes) -> int | None:
    limit = min(len(left), len(right))
    for idx in range(limit):
        if left[idx] != right[idx]:
            return idx
    if len(left) != len(right):
        return limit
    return None


def _snippet_at_offset(data: bytes, offset: int | None, *, radius: int = 120) -> str:
    if offset is None:
        text = data.decode("utf-8", errors="replace")
        return text[:400] if len(text) > 400 else text
    start = max(0, offset - radius)
    end = min(len(data), offset + radius)
    return data[start:end].decode("utf-8", errors="replace")


def _first_diff(left: Any, right: Any, path: str) -> tuple[str, str]:
    if type(left) is not type(right):
        return path, f"type mismatch: {type(left).__name__} vs {type(right).__name__}"
    if isinstance(left, dict):
        left_keys = set(left)
        right_keys = set(right)
        if left_keys != right_keys:
            only_left = sorted(left_keys - right_keys)
            only_right = sorted(right_keys - left_keys)
            if len(only_right) == 1 and not only_left:
                key = only_right[0]
                return f"{path}.{key}", f"key present in target only: {key!r}"
            if len(only_left) == 1 and not only_right:
                key = only_left[0]
                return f"{path}.{key}", f"key present in source only: {key!r}"
            return path, f"keys differ (only in source: {only_left}, only in target: {only_right})"
        for key in sorted(left_keys):
            child_path, detail = _first_diff(left[key], right[key], f"{path}.{key}")
            if detail:
                return child_path, detail
        return path, ""
    if isinstance(left, list):
        if len(left) != len(right):
            return path, f"array length mismatch: {len(left)} vs {len(right)}"
        left_counts = Counter(dumps_bytes(item) for item in left)
        right_counts = Counter(dumps_bytes(item) for item in right)
        if left_counts != right_counts:
            only_left = left_counts - right_counts
            only_right = right_counts - left_counts
            return path, f"array multiset mismatch (extra in source: {len(only_left)}, extra in target: {len(only_right)})"
        return path, ""
    if left != right:
        return path, f"value mismatch: {left!r} vs {right!r}"
    return path, ""


def load_json_file(path: Path) -> Any:
    """Parse a single JSON document from *path*."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValidationBadRequestError(f"Cannot read JSON file: {path}") from exc
    if not raw.strip():
        raise ValidationBadRequestError(f"Empty JSON file: {path}")
    try:
        return loads_bytes(raw)
    except (ValueError, TypeError) as exc:
        text = raw.decode("utf-8", errors="replace")
        try:
            return loads_str(text)
        except (ValueError, TypeError):
            raise ValidationBadRequestError(f"Invalid JSON in {path.name}: {exc}") from exc


def compare_json_documents(source: Any, target: Any) -> tuple[bool, bytes, bytes]:
    """Return (is_match, canonical_source_bytes, canonical_target_bytes)."""
    src_canon = canonical_json_bytes(source)
    tgt_canon = canonical_json_bytes(target)
    return json_values_equal(source, target), src_canon, tgt_canon


def _cell_str(obj: Any, *, limit: int = 500) -> str:
    text = dumps_bytes(canonical_json_value(obj)).decode("utf-8")
    if len(text) <= limit:
        return text
    return text[:limit]


def _append_row(
    rows: list[dict[str, Any]],
    summary: dict[str, int],
    *,
    uid: str,
    mismatch_type: str,
    column_name: str | None,
    source_value: Any | None,
    target_value: Any | None,
    path: str,
) -> None:
    summary[mismatch_type] += 1
    rows.append({
        "uid": uid,
        "mismatch_type": mismatch_type,
        "column_name": column_name,
        "source_value": _cell_str(source_value) if source_value is not None else None,
        "target_value": _cell_str(target_value) if target_value is not None else None,
        "row_detail": dumps_bytes({"path": path}).decode("utf-8"),
    })


def _field_indexed_list(items: list[Any]) -> dict[str, Any] | None:
    """Map ``field`` -> item when the list is a list of unique field-keyed objects."""
    if not isinstance(items, list):
        return None
    out: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, dict):
            return None
        field = item.get("field")
        if not isinstance(field, str) or not field:
            return None
        if field in out:
            return None
        out[field] = item
    return out


def _diff_field_indexed_lists(
    rows: list[dict[str, Any]],
    summary: dict[str, int],
    *,
    source_list: list[Any],
    target_list: list[Any],
    path: str,
    column_name: str,
) -> None:
    src_map = _field_indexed_list(source_list) or {}
    tgt_map = _field_indexed_list(target_list) or {}
    for field in sorted(set(src_map) - set(tgt_map)):
        _append_row(
            rows,
            summary,
            uid=field,
            mismatch_type="missing_in_target",
            column_name=column_name,
            source_value=src_map[field],
            target_value=None,
            path=f"{path}[field={field}]",
        )
    for field in sorted(set(tgt_map) - set(src_map)):
        _append_row(
            rows,
            summary,
            uid=field,
            mismatch_type="extra_in_target",
            column_name=column_name,
            source_value=None,
            target_value=tgt_map[field],
            path=f"{path}[field={field}]",
        )
    for field in sorted(set(src_map) & set(tgt_map)):
        if not json_values_equal(src_map[field], tgt_map[field]):
            _append_row(
                rows,
                summary,
                uid=field,
                mismatch_type="value_mismatch",
                column_name=column_name,
                source_value=src_map[field],
                target_value=tgt_map[field],
                path=f"{path}[field={field}]",
            )


def _diff_multiset_lists(
    rows: list[dict[str, Any]],
    summary: dict[str, int],
    *,
    source_list: list[Any],
    target_list: list[Any],
    path: str,
    column_name: str,
) -> None:
    src_items = [canonical_json_value(item) for item in source_list]
    tgt_items = [canonical_json_value(item) for item in target_list]
    src_by_fp: dict[bytes, Any] = {}
    tgt_by_fp: dict[bytes, Any] = {}
    for raw, canon in zip(source_list, src_items, strict=False):
        src_by_fp.setdefault(dumps_bytes(canon), raw)
    for raw, canon in zip(target_list, tgt_items, strict=False):
        tgt_by_fp.setdefault(dumps_bytes(canon), raw)

    src_counts = Counter(dumps_bytes(item) for item in src_items)
    tgt_counts = Counter(dumps_bytes(item) for item in tgt_items)
    idx = 0
    for fp, count in sorted((src_counts - tgt_counts).items(), key=lambda kv: kv[0]):
        for _ in range(count):
            idx += 1
            item = src_by_fp[fp]
            uid = str(item.get("field")) if isinstance(item, dict) and item.get("field") else f"{path}[{idx}]"
            _append_row(
                rows,
                summary,
                uid=uid,
                mismatch_type="missing_in_target",
                column_name=column_name,
                source_value=item,
                target_value=None,
                path=f"{path}[{uid}]",
            )
    idx = 0
    for fp, count in sorted((tgt_counts - src_counts).items(), key=lambda kv: kv[0]):
        for _ in range(count):
            idx += 1
            item = tgt_by_fp[fp]
            uid = str(item.get("field")) if isinstance(item, dict) and item.get("field") else f"{path}[{idx}]"
            _append_row(
                rows,
                summary,
                uid=uid,
                mismatch_type="extra_in_target",
                column_name=column_name,
                source_value=None,
                target_value=item,
                path=f"{path}[{uid}]",
            )


def _collect_diff(
    rows: list[dict[str, Any]],
    summary: dict[str, int],
    *,
    source: Any,
    target: Any,
    path: str,
    column_name: str,
) -> None:
    if json_values_equal(source, target):
        return

    if isinstance(source, dict) and isinstance(target, dict):
        src_c = canonical_json_value(source)
        tgt_c = canonical_json_value(target)
        for key in sorted(set(src_c) - set(tgt_c)):
            child = f"{path}.{key}"
            _append_row(
                rows,
                summary,
                uid=key,
                mismatch_type="missing_in_target",
                column_name=key,
                source_value=source[key],
                target_value=None,
                path=child,
            )
        for key in sorted(set(tgt_c) - set(src_c)):
            child = f"{path}.{key}"
            _append_row(
                rows,
                summary,
                uid=key,
                mismatch_type="extra_in_target",
                column_name=key,
                source_value=None,
                target_value=target[key],
                path=child,
            )
        for key in sorted(set(src_c) & set(tgt_c)):
            _collect_diff(
                rows,
                summary,
                source=source[key],
                target=target[key],
                path=f"{path}.{key}",
                column_name=key,
            )
        return

    if isinstance(source, list) and isinstance(target, list):
        if _field_indexed_list(source) is not None and _field_indexed_list(target) is not None:
            _diff_field_indexed_lists(
                rows,
                summary,
                source_list=source,
                target_list=target,
                path=path,
                column_name=column_name,
            )
        else:
            _diff_multiset_lists(
                rows,
                summary,
                source_list=source,
                target_list=target,
                path=path,
                column_name=column_name,
            )
        return

    _append_row(
        rows,
        summary,
        uid=path.removeprefix("$.").replace(".", "_") or "document",
        mismatch_type="value_mismatch",
        column_name=column_name,
        source_value=source,
        target_value=target,
        path=path,
    )


def collect_json_mismatches(source: Any, target: Any) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Enumerate JSON differences with CSV-compatible mismatch types and counts."""
    summary = {"missing_in_target": 0, "extra_in_target": 0, "value_mismatch": 0}
    rows: list[dict[str, Any]] = []
    if json_values_equal(source, target):
        return summary, rows
    _collect_diff(rows, summary, source=source, target=target, path="$", column_name="json")
    return summary, rows
