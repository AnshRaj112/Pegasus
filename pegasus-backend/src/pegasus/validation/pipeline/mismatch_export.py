# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T09:01:26Z
# --- END GENERATED FILE METADATA ---

"""Export full mismatch rows from reconciliation spill files to NDJSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pegasus.validation.comparators.models import MismatchType
from pegasus.validation.pipeline.arrow_spill import partition_has_arrow, read_arrow_partition
from pegasus.validation.pipeline.drilldown_cache import load_drilldown_lookup
from pegasus.validation.pipeline.partition_reconcile import _column_values_match
from pegasus.validation.pipeline.spill import iter_partition, list_partition_ids


@dataclass(frozen=True, slots=True)
class MismatchExportStats:
    missing_in_target: int = 0
    extra_in_target: int = 0
    value_mismatch: int = 0

    @property
    def total(self) -> int:
        return self.missing_in_target + self.extra_in_target + self.value_mismatch

    def to_summary(self) -> dict[str, int]:
        return {
            MismatchType.MISSING_IN_TARGET.value: self.missing_in_target,
            MismatchType.EXTRA_IN_TARGET.value: self.extra_in_target,
            MismatchType.VALUE_MISMATCH.value: self.value_mismatch,
        }


def _serialize_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _record_payload(
    uid: str,
    payload: dict[str, Any] | None,
    *,
    drilldown: dict[str, str] | None = None,
) -> dict[str, Any]:
    record = {"uid": uid}
    if drilldown:
        record.update(drilldown)
    if payload:
        record.update({k: v for k, v in payload.items() if not str(k).startswith("_")})
    return record


def _write_line(fp, row: dict[str, Any]) -> None:
    fp.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_partition_entries(
    path: Path,
    *,
    compare_columns: list[str],
) -> dict[str, dict[str, Any]]:
    """Load partition rows as uid -> payload (arrow spill stores fingerprint only)."""
    if not path.is_file():
        return {}
    if partition_has_arrow(path):
        frame = read_arrow_partition(path)
        if frame is None or frame.is_empty():
            return {}
        entries: dict[str, dict[str, Any]] = {}
        for row in frame.iter_rows(named=True):
            uid = str(row.get("identity") or "")
            if not uid:
                continue
            entries[uid] = {"_fp": int(row.get("fingerprint") or 0)}
        return entries

    entries = {}
    for key, _fp, payload in iter_partition(path, compare_columns=compare_columns):
        data = dict(payload or {})
        data["_fp"] = int.from_bytes(_fp[:8].ljust(8, b"\x00"), "big", signed=False) if _fp else 0
        entries[key] = data
    return entries


def export_workspace_mismatches_ndjson(
    workspace: Path,
    out_path: Path,
    *,
    compare_columns: list[str],
) -> MismatchExportStats:
    """Scan spill partitions and write every mismatch row with row_detail payloads."""
    workspace = Path(workspace)
    if not workspace.is_dir():
        return MismatchExportStats()

    active = list_partition_ids(workspace, "source") | list_partition_ids(workspace, "target")
    if not active:
        return MismatchExportStats()

    src_drilldown = load_drilldown_lookup(workspace, "source", compare_columns)
    tgt_drilldown = load_drilldown_lookup(workspace, "target", compare_columns)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    missing = 0
    extra = 0
    value_mismatch = 0

    with out_path.open("w", encoding="utf-8") as fp:
        for pid in sorted(active):
            src_path = workspace / "source" / f"part_{pid:05d}.bin"
            tgt_path = workspace / "target" / f"part_{pid:05d}.bin"

            src_payload = _load_partition_entries(src_path, compare_columns=compare_columns)
            tgt_payload = _load_partition_entries(tgt_path, compare_columns=compare_columns)

            src_keys = set(src_payload)
            tgt_keys = set(tgt_payload)

            for key in src_keys - tgt_keys:
                source_record = _record_payload(
                    key,
                    src_payload.get(key),
                    drilldown=src_drilldown.get(key),
                )
                _write_line(
                    fp,
                    {
                        "uid": key,
                        "mismatch_type": MismatchType.MISSING_IN_TARGET.value,
                        "column_name": None,
                        "source_value": None,
                        "target_value": None,
                        "row_detail": json.dumps(
                            {"source_record": source_record, "target_record": None},
                            ensure_ascii=False,
                        ),
                    },
                )
                missing += 1

            for key in tgt_keys - src_keys:
                target_record = _record_payload(
                    key,
                    tgt_payload.get(key),
                    drilldown=tgt_drilldown.get(key),
                )
                _write_line(
                    fp,
                    {
                        "uid": key,
                        "mismatch_type": MismatchType.EXTRA_IN_TARGET.value,
                        "column_name": None,
                        "source_value": None,
                        "target_value": None,
                        "row_detail": json.dumps(
                            {"source_record": None, "target_record": target_record},
                            ensure_ascii=False,
                        ),
                    },
                )
                extra += 1

            for key in src_keys & tgt_keys:
                source_data = dict(src_payload[key])
                target_data = dict(tgt_payload[key])
                src_cells = {**src_drilldown.get(key, {}), **{
                    col: source_data[col] for col in compare_columns if col in source_data
                }}
                tgt_cells = {**tgt_drilldown.get(key, {}), **{
                    col: target_data[col] for col in compare_columns if col in target_data
                }}
                has_column_payload = bool(src_cells or tgt_cells) or any(
                    col in source_data or col in target_data for col in compare_columns
                )
                fp_diff = source_data.get("_fp") != target_data.get("_fp")
                if not has_column_payload and not fp_diff:
                    continue

                source_record = _record_payload(key, source_data, drilldown=src_cells or None)
                target_record = _record_payload(key, target_data, drilldown=tgt_cells or None)
                row_detail = json.dumps(
                    {"source_record": source_record, "target_record": target_record},
                    ensure_ascii=False,
                )
                wrote = False
                for col in compare_columns:
                    source_value = src_cells.get(col, source_data.get(col))
                    target_value = tgt_cells.get(col, target_data.get(col))
                    if _column_values_match(col, source_value, target_value):
                        continue
                    wrote = True
                    _write_line(
                        fp,
                        {
                            "uid": key,
                            "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                            "column_name": col,
                            "source_value": _serialize_value(source_value),
                            "target_value": _serialize_value(target_value),
                            "row_detail": row_detail,
                        },
                    )
                    value_mismatch += 1
                # Skip fingerprint-only rows when every compare column matches under policy.

    return MismatchExportStats(
        missing_in_target=missing,
        extra_in_target=extra,
        value_mismatch=value_mismatch,
    )
