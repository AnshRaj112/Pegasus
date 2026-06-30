# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T14:52:27Z
# --- END GENERATED FILE METADATA ---

"""Top-level JSON parent discovery and mapping suggestions for the wizard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pegasus.validation.json_compare import JSON_DOCUMENT_UID, load_json_payload


def _json_value_type(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


def list_root_parents(
    payload: Any,
    *,
    mode: str,
    uid_column: str,
    max_ndjson_records: int = 100,
) -> list[dict[str, str]]:
    """Return top-level JSON parents with a coarse value type."""
    if mode == "document":
        if isinstance(payload, dict):
            return [
                {"key": str(key), "value_type": _json_value_type(payload[key])}
                for key in payload.keys()
            ]
        return [{"key": "$", "value_type": _json_value_type(payload)}]

    keys_seen: dict[str, str] = {}
    if not isinstance(payload, list):
        return []
    uid_key = (uid_column or JSON_DOCUMENT_UID).strip() or JSON_DOCUMENT_UID
    for record in payload[:max_ndjson_records]:
        if not isinstance(record, dict):
            continue
        for key, value in record.items():
            if key == uid_key:
                continue
            if key not in keys_seen:
                keys_seen[key] = _json_value_type(value)
    return [{"key": key, "value_type": keys_seen[key]} for key in sorted(keys_seen, key=str)]


def suggest_parent_mappings(
    source_parents: list[str],
    target_parents: list[str],
) -> list[dict[str, Any]]:
    """Auto-pair parents by identical key name; leave unmatched source keys unmapped."""
    target_set = set(target_parents)
    used_targets: set[str] = set()
    rows: list[dict[str, Any]] = []

    for source_parent in source_parents:
        if source_parent in target_set and source_parent not in used_targets:
            rows.append({
                "source_parent": source_parent,
                "target_parent": source_parent,
                "ignored": False,
            })
            used_targets.add(source_parent)
        else:
            rows.append({
                "source_parent": source_parent,
                "target_parent": None,
                "ignored": False,
            })

    for target_parent in target_parents:
        if target_parent not in used_targets and target_parent not in source_parents:
            rows.append({
                "source_parent": None,
                "target_parent": target_parent,
                "ignored": True,
            })

    return rows


def parent_mappings_from_column_mappings(
    mappings: list[dict[str, Any]] | list[Any] | None,
) -> list[tuple[str, str]]:
    """Extract (source_parent, target_parent) pairs from wizard column mappings."""
    if not mappings:
        return []
    pairs: list[tuple[str, str]] = []
    for item in mappings:
        if isinstance(item, dict):
            source = str(item.get("source_column") or "").strip()
            target = str(item.get("target_column") or source).strip()
        else:
            source = str(getattr(item, "source_column", "") or "").strip()
            target = str(getattr(item, "target_column", "") or source).strip()
        if source and target:
            pairs.append((source, target))
    return pairs


def align_roots_with_parent_mappings(
    source: Any,
    target: Any,
    mappings: list[tuple[str, str]] | None,
) -> tuple[Any, Any]:
    """Restrict comparison to mapped top-level parents, renaming source keys to target keys."""
    if not mappings:
        return source, target
    if not isinstance(source, dict) or not isinstance(target, dict):
        return source, target

    aligned_source: dict[str, Any] = {}
    aligned_target: dict[str, Any] = {}
    for source_key, target_key in mappings:
        if source_key in source:
            aligned_source[target_key] = source[source_key]
        if target_key in target:
            aligned_target[target_key] = target[target_key]
    return aligned_source, aligned_target


def build_json_parent_preview(
    source_path: Path,
    target_path: Path,
    *,
    uid_column: str = JSON_DOCUMENT_UID,
) -> dict[str, Any]:
    """Load two JSON files and return parent lists plus suggested mappings."""
    src_mode, src_payload = load_json_payload(source_path)
    tgt_mode, tgt_payload = load_json_payload(target_path)
    if src_mode != tgt_mode:
        raise ValueError("Source and target must both be single JSON documents or both be NDJSON")

    uid_key = (uid_column or JSON_DOCUMENT_UID).strip() or JSON_DOCUMENT_UID
    source_fields = list_root_parents(src_payload, mode=src_mode, uid_column=uid_key)
    target_fields = list_root_parents(tgt_payload, mode=tgt_mode, uid_column=uid_key)
    source_keys = [field["key"] for field in source_fields]
    target_keys = [field["key"] for field in target_fields]
    source_types = {field["key"]: field["value_type"] for field in source_fields}
    target_types = {field["key"]: field["value_type"] for field in target_fields}

    suggested = suggest_parent_mappings(source_keys, target_keys)
    for row in suggested:
        sp = row.get("source_parent")
        tp = row.get("target_parent")
        if sp:
            row["source_type"] = source_types.get(sp)
        if tp:
            row["target_type"] = target_types.get(tp)

    suggested_uid = None
    if src_mode == "ndjson":
        for candidate in ("id", "uid", "record_id", "key"):
            if candidate in source_keys and candidate in target_keys:
                suggested_uid = candidate
                break

    return {
        "document_mode": src_mode,
        "source_parents": source_fields,
        "target_parents": target_fields,
        "suggested_mappings": suggested,
        "suggested_uid_field": suggested_uid,
    }
