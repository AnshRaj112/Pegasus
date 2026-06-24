# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:22:13Z
# --- END GENERATED FILE METADATA ---

"""Export full mismatch rows from reconciliation spill files to NDJSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pegasus.validation.comparators.models import MismatchType, VALUE_MISMATCH_ROWS_SUMMARY_KEY
from pegasus.validation.pipeline.arrow_spill import partition_has_arrow, read_arrow_partition
from pegasus.validation.pipeline.drilldown_cache import load_drilldown_lookup
from pegasus.validation.pipeline.partition_reconcile import _column_values_match
from pegasus.validation.pipeline.spill import iter_partition, list_partition_ids


@dataclass(frozen=True, slots=True)
class MismatchExportStats:
    missing_in_target: int = 0
    extra_in_target: int = 0
    value_mismatch: int = 0
    value_mismatch_rows: int = 0

    @property
    def total(self) -> int:
        return self.missing_in_target + self.extra_in_target + self.value_mismatch

    def to_summary(self) -> dict[str, int]:
        return {
            MismatchType.MISSING_IN_TARGET.value: self.missing_in_target,
            MismatchType.EXTRA_IN_TARGET.value: self.extra_in_target,
            MismatchType.VALUE_MISMATCH.value: self.value_mismatch,
            VALUE_MISMATCH_ROWS_SUMMARY_KEY: self.value_mismatch_rows,
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


def _collect_mismatch_keys_for_pids(
    workspace: Path,
    pids: list[int],
    *,
    compare_columns: list[str],
) -> set[str]:
    """Find UIDs needing drilldown within the given partition ids."""
    needed: set[str] = set()
    for pid in pids:
        src_path = workspace / "source" / f"part_{pid:05d}.bin"
        tgt_path = workspace / "target" / f"part_{pid:05d}.bin"
        src_payload = _load_partition_entries(src_path, compare_columns=compare_columns)
        tgt_payload = _load_partition_entries(tgt_path, compare_columns=compare_columns)
        src_keys = set(src_payload)
        tgt_keys = set(tgt_payload)
        needed |= src_keys - tgt_keys
        needed |= tgt_keys - src_keys
        for key in src_keys & tgt_keys:
            if src_payload[key].get("_fp") != tgt_payload[key].get("_fp"):
                needed.add(key)
    return needed


def _collect_mismatch_keys(
    workspace: Path,
    *,
    compare_columns: list[str],
) -> set[str]:
    """Lightweight pass over spill partitions to find UIDs that need drilldown."""
    active = sorted(list_partition_ids(workspace, "source") | list_partition_ids(workspace, "target"))
    return _collect_mismatch_keys_for_pids(workspace, active, compare_columns=compare_columns)


def _export_partitions_to_fp(
    fp,
    workspace: Path,
    pids: list[int],
    *,
    compare_columns: list[str],
    sensitive_columns: set[str] | None,
    src_drilldown: dict[str, dict[str, str]],
    tgt_drilldown: dict[str, dict[str, str]],
) -> MismatchExportStats:
    missing = 0
    extra = 0
    value_mismatch = 0
    value_mismatch_row_uids: set[str] = set()
    for pid in sorted(pids):
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
            for col in compare_columns:
                source_value = src_cells.get(col, source_data.get(col))
                target_value = tgt_cells.get(col, target_data.get(col))
                if _column_values_match(col, source_value, target_value):
                    continue
                sv = _serialize_value(source_value)
                tv = _serialize_value(target_value)
                if sensitive_columns and col in sensitive_columns:
                    sv = "****" if sv else sv
                    tv = "****" if tv else tv
                _write_line(
                    fp,
                    {
                        "uid": key,
                        "mismatch_type": MismatchType.VALUE_MISMATCH.value,
                        "column_name": col,
                        "source_value": sv,
                        "target_value": tv,
                        "row_detail": row_detail,
                    },
                )
                value_mismatch += 1
                value_mismatch_row_uids.add(key)

    return MismatchExportStats(
        missing_in_target=missing,
        extra_in_target=extra,
        value_mismatch=value_mismatch,
        value_mismatch_rows=len(value_mismatch_row_uids),
    )


def export_partitions_to_ndjson(
    workspace: Path,
    out_path: Path,
    *,
    compare_columns: list[str],
    pids: list[int],
    append: bool = False,
    sensitive_columns: set[str] | None = None,
) -> MismatchExportStats:
    """Export mismatches for specific partition ids; append mode for wave processing."""
    workspace = Path(workspace)
    if not workspace.is_dir() or not pids:
        return MismatchExportStats()

    needed_keys = _collect_mismatch_keys_for_pids(workspace, pids, compare_columns=compare_columns)
    if needed_keys:
        src_drilldown = load_drilldown_lookup(
            workspace, "source", compare_columns, keys=needed_keys
        )
        tgt_drilldown = load_drilldown_lookup(
            workspace, "target", compare_columns, keys=needed_keys
        )
    else:
        src_drilldown = {}
        tgt_drilldown = {}

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append and out_path.is_file() else "w"
    with out_path.open(mode, encoding="utf-8") as fp:
        return _export_partitions_to_fp(
            fp,
            workspace,
            pids,
            compare_columns=compare_columns,
            sensitive_columns=sensitive_columns,
            src_drilldown=src_drilldown,
            tgt_drilldown=tgt_drilldown,
        )


def _parse_row_detail_obj(raw: object) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _record_has_compare_columns(record: object, compare_columns: list[str]) -> bool:
    if not isinstance(record, dict):
        return False
    return any(col in record and str(record.get(col) or "") not in ("", "__NULL__") for col in compare_columns)


def ndjson_row_detail_lacks_columns(path: Path, compare_columns: list[str]) -> bool:
    """True when NDJSON rows are missing compare-column values in row_detail."""
    if not compare_columns or not path.is_file():
        return False
    try:
        with path.open(encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                mtype = str(row.get("mismatch_type") or "")
                detail = _parse_row_detail_obj(row.get("row_detail"))
                if mtype == MismatchType.MISSING_IN_TARGET.value:
                    if not _record_has_compare_columns(detail.get("source_record"), compare_columns):
                        return True
                    continue
                if mtype == MismatchType.EXTRA_IN_TARGET.value:
                    if not _record_has_compare_columns(detail.get("target_record"), compare_columns):
                        return True
                    continue
                if mtype == MismatchType.VALUE_MISMATCH.value:
                    col = str(row.get("column_name") or "")
                    if col and (
                        row.get("source_value") not in (None, "")
                        or row.get("target_value") not in (None, "")
                    ):
                        return False
                    if not _record_has_compare_columns(detail.get("source_record"), compare_columns):
                        return True
                    if not _record_has_compare_columns(detail.get("target_record"), compare_columns):
                        return True
                    return False
    except (OSError, json.JSONDecodeError):
        return True
    return False


def enrich_mismatch_ndjson_from_lookups(
    path: Path,
    *,
    compare_columns: list[str],
    source_lookup: dict[str, dict[str, str]],
    target_lookup: dict[str, dict[str, str]],
) -> int:
    """Fill missing row_detail cells from uid -> column maps; returns rows updated."""
    if not path.is_file() or not compare_columns:
        return 0
    updated = 0
    out_lines: list[str] = []
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            raw = line.strip()
            if not raw:
                continue
            row = json.loads(raw)
            uid = str(row.get("uid") or "")
            mtype = str(row.get("mismatch_type") or "")
            detail = _parse_row_detail_obj(row.get("row_detail"))
            changed = False

            if mtype == MismatchType.MISSING_IN_TARGET.value:
                src_rec = dict(detail.get("source_record") or {"uid": uid})
                if uid and not _record_has_compare_columns(src_rec, compare_columns):
                    cells = source_lookup.get(uid, {})
                    if cells:
                        src_rec = {"uid": uid, **cells}
                        detail["source_record"] = src_rec
                        detail.setdefault("target_record", None)
                        changed = True
            elif mtype == MismatchType.EXTRA_IN_TARGET.value:
                tgt_rec = dict(detail.get("target_record") or {"uid": uid})
                if uid and not _record_has_compare_columns(tgt_rec, compare_columns):
                    cells = target_lookup.get(uid, {})
                    if cells:
                        tgt_rec = {"uid": uid, **cells}
                        detail["target_record"] = tgt_rec
                        detail.setdefault("source_record", None)
                        changed = True
            elif mtype == MismatchType.VALUE_MISMATCH.value:
                src_rec = dict(detail.get("source_record") or {"uid": uid})
                tgt_rec = dict(detail.get("target_record") or {"uid": uid})
                src_cells = source_lookup.get(uid, {})
                tgt_cells = target_lookup.get(uid, {})
                if src_cells and not _record_has_compare_columns(src_rec, compare_columns):
                    src_rec = {"uid": uid, **src_cells}
                    changed = True
                if tgt_cells and not _record_has_compare_columns(tgt_rec, compare_columns):
                    tgt_rec = {"uid": uid, **tgt_cells}
                    changed = True
                if changed:
                    detail["source_record"] = src_rec
                    detail["target_record"] = tgt_rec
                col = str(row.get("column_name") or "")
                if col and col in src_rec and not row.get("source_value"):
                    row["source_value"] = _serialize_value(src_rec.get(col))
                    changed = True
                if col and col in tgt_rec and not row.get("target_value"):
                    row["target_value"] = _serialize_value(tgt_rec.get(col))
                    changed = True

            if changed:
                row["row_detail"] = json.dumps(detail, ensure_ascii=False)
                updated += 1
            out_lines.append(json.dumps(row, ensure_ascii=False))

    if updated > 0:
        path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
    return updated


def export_workspace_mismatches_ndjson(
    workspace: Path,
    out_path: Path,
    *,
    compare_columns: list[str],
    sensitive_columns: set[str] | None = None,
) -> MismatchExportStats:
    """Scan spill partitions and write every mismatch row with row_detail payloads."""
    workspace = Path(workspace)
    if not workspace.is_dir():
        return MismatchExportStats()

    active = sorted(list_partition_ids(workspace, "source") | list_partition_ids(workspace, "target"))
    if not active:
        return MismatchExportStats()

    return export_partitions_to_ndjson(
        workspace,
        out_path,
        compare_columns=compare_columns,
        pids=active,
        append=False,
        sensitive_columns=sensitive_columns,
    )
