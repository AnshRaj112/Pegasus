# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-15T16:31:14+05:30
# --- END GENERATED FILE METADATA ---

"""Resolve API column_mappings into logical compare fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pegasus.schemas.validation import ColumnMapping

_FIELD_SEP = "\x1f"


@dataclass(frozen=True, slots=True)
class FieldMapping:
    """One logical compare slot (reported under *key*)."""

    key: str
    source_columns: tuple[str, ...]
    target_columns: tuple[str, ...]
    mode: str = "auto"
    complex: bool = False
    order_sensitive: bool = False


def _dedupe(names: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(n.strip() for n in names if n and n.strip()))


def resolve_field_mapping(m: ColumnMapping, *, scanned_complex: set[str]) -> FieldMapping | None:
    key = (m.source_column or "").strip()
    if not key:
        return None

    if m.source_columns:
        src_cols = _dedupe(list(m.source_columns))
    else:
        src_cols = _dedupe([key]) if key else ()

    tgt_extra = [c.strip() for c in (m.target_columns or []) if c and c.strip()]
    primary_tgt = (m.target_column or "").strip()
    if primary_tgt:
        tgt_cols = _dedupe([primary_tgt, *tgt_extra])
    elif tgt_extra:
        tgt_cols = _dedupe(tgt_extra)
    else:
        tgt_cols = _dedupe([key]) if key else ()

    mode = (m.compare_mode or "auto").lower()
    complex_mode = mode == "structured" or (mode == "auto" and key in scanned_complex)
    return FieldMapping(
        key=key,
        source_columns=src_cols,
        target_columns=tuple(tgt_cols),
        mode=mode,
        complex=complex_mode,
        order_sensitive=m.structured_order_sensitive,
    )


def uid_column_names(uid_column: str) -> set[str]:
    return {c.strip() for c in uid_column.split(",") if c.strip()}


def resolve_field_mappings(
    mappings: list[ColumnMapping] | None,
    *,
    scanned_complex: set[str],
    schema_names: list[str] | None = None,
    uid_column: str = "",
) -> list[FieldMapping]:
    """Build ordered logical fields from explicit mappings or schema column names."""
    uid_cols = uid_column_names(uid_column)
    if mappings:
        fields: list[FieldMapping] = []
        for m in mappings:
            fm = resolve_field_mapping(m, scanned_complex=scanned_complex)
            if fm is None or fm.key in uid_cols:
                continue
            fields.append(fm)
        return fields

    if not schema_names:
        return []
    return [
        FieldMapping(key=col, source_columns=(col,), target_columns=(col,))
        for col in schema_names
        if col not in uid_cols
    ]


def logical_compare_keys(fields: list[FieldMapping]) -> list[str]:
    return [f.key for f in fields]


def physical_columns_for_side(fields: list[FieldMapping], side: str) -> list[str]:
    cols: list[str] = []
    for fm in fields:
        physical = fm.source_columns if side == "source" else fm.target_columns
        for col in physical:
            if col not in cols:
                cols.append(col)
    return cols


def uses_non_trivial_mapping(fields: list[FieldMapping]) -> bool:
    return any(
        fm.source_columns != fm.target_columns
        or len(fm.source_columns) > 1
        or len(fm.target_columns) > 1
        for fm in fields
    )


def join_canonical_parts(parts: list[str]) -> str:
    if not parts:
        return "__NULL__"
    if len(parts) == 1:
        return parts[0]
    return " ".join(parts)


def target_canonical_from_parts(parts: list[str]) -> str:
    """Fingerprint-friendly target canonical for 1:N mappings."""
    if not parts:
        return "__NULL__"
    if len(parts) == 1:
        return parts[0]
    if len(set(parts)) == 1:
        return parts[0]
    return _FIELD_SEP.join(parts)
