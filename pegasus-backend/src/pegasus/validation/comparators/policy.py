# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-16T10:15:03Z
# --- END GENERATED FILE METADATA ---

"""Per-column compare rules wired from API column_mappings into the pipeline."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator, Literal

from pegasus.validation.comparators.core import _lit, eq
from pegasus.validation.comparators.mapping_resolver import (
    FieldMapping,
    join_canonical_parts,
    logical_compare_keys,
    physical_columns_for_side,
    resolve_field_mappings,
    target_canonical_from_parts,
    uses_non_trivial_mapping,
)

if TYPE_CHECKING:
    from pegasus.schemas.validation import ColumnMapping

_C = (list, dict, tuple)
_active: ContextVar[ComparePolicy | None] = ContextVar("compare_policy", default=None)


@dataclass(frozen=True, slots=True)
class ColumnRule:
    mode: str = "auto"
    complex: bool = False
    order_sensitive: bool = False
    target_column: str | None = None
    source_columns: tuple[str, ...] = ()
    target_columns: tuple[str, ...] = ()
    source_regex_pattern: str | None = None
    source_regex_replacement: str = ""
    target_regex_pattern: str | None = None
    target_regex_replacement: str = ""
    source_strip_prefix: str | None = None
    target_strip_prefix: str | None = None
    is_sensitive: bool = False


@dataclass(slots=True)
class ComparePolicy:
    rules: dict[str, ColumnRule] = field(default_factory=dict)
    fields: list[FieldMapping] = field(default_factory=list)

    def rule_for(self, col: str) -> ColumnRule:
        return self.rules.get(col, ColumnRule())

    @property
    def compare_keys(self) -> list[str]:
        if self.fields:
            return logical_compare_keys(self.fields)
        return list(self.rules.keys())

    @property
    def needs_smart_canonical(self) -> bool:
        return any(r.mode != "text" or r.complex for r in self.rules.values())

    @property
    def has_non_trivial_mapping(self) -> bool:
        return uses_non_trivial_mapping(self.fields)

    def physical_columns(self, side: Literal["source", "target"]) -> list[str]:
        if self.fields:
            return physical_columns_for_side(self.fields, side)
        return self.compare_keys

    def _preprocess_value(self, key: str, value: Any, *, side: Literal["source", "target"]) -> Any:
        from pegasus.validation.comparators.core import apply_value_transform

        r = self.rule_for(key)
        if side == "source":
            return apply_value_transform(
                value,
                pattern=r.source_regex_pattern,
                replacement=r.source_regex_replacement,
                strip_prefix=r.source_strip_prefix,
            )
        return apply_value_transform(
            value,
            pattern=r.target_regex_pattern,
            replacement=r.target_regex_replacement,
            strip_prefix=r.target_strip_prefix,
        )

    def _canonical_cell(self, key: str, value: Any) -> str:
        from pegasus.validation.comparators.core import _date_candidates, canonical_key

        r = self.rule_for(key)
        complex_mode = r.complex or r.mode == "structured"
        if not complex_mode and r.mode == "text":
            if value is None:
                return "__NULL__"
            text = str(value).strip()
            if text.lower() in ("", "null", "none", "na", "n/a"):
                return "__NULL__"
            return text
        if not complex_mode and r.mode == "auto":
            if value is None:
                return "__NULL__"
            candidates = _date_candidates(value)
            if len(candidates) == 1:
                return next(iter(candidates)).isoformat()
            if candidates:
                return min(candidates).isoformat()
            text = str(value).strip()
            if text.lower() in ("", "null", "none", "na", "n/a"):
                return "__NULL__"
            return text
        return canonical_key(
            value,
            mode=r.mode,
            complex_mode=complex_mode,
            order=r.order_sensitive if r.complex else False,
        )

    def canonical_side_part(
        self,
        record: dict[str, Any],
        key: str,
        *,
        side: Literal["source", "target"],
    ) -> str:
        fm = self.field_for(key)
        if fm is None:
            return self._canonical_cell(key, self._preprocess_value(key, record.get(key), side=side))
        physical = fm.source_columns if side == "source" else fm.target_columns
        parts = [
            self._canonical_cell(key, self._preprocess_value(key, record.get(col), side=side))
            for col in physical
        ]
        if side == "source":
            return join_canonical_parts(parts)
        return target_canonical_from_parts(parts)

    def canonical_parts_for_record(
        self,
        record: dict[str, Any],
        *,
        side: Literal["source", "target"],
        keys: list[str] | None = None,
    ) -> list[str]:
        compare_keys = keys if keys is not None else self.compare_keys
        return [self.canonical_side_part(record, key, side=side) for key in compare_keys]

    def values_equal_mapped(
        self,
        key: str,
        source_record: dict[str, Any],
        target_record: dict[str, Any],
    ) -> bool:
        src = self.canonical_side_part(source_record, key, side="source")
        tgt = self.canonical_side_part(target_record, key, side="target")
        return src == tgt

    def values_equal(self, col: str, a: Any, b: Any) -> bool:
        r = self.rule_for(col)
        return eq(
            a,
            b,
            order=r.order_sensitive if r.complex else False,
            complex_mode=r.complex or r.mode == "structured",
        )

    def is_sensitive_column(self, col: str) -> bool:
        return self.rule_for(col).is_sensitive

    def mask_if_sensitive(self, col: str, value: str | None) -> str | None:
        if value and self.is_sensitive_column(col):
            return "****"
        return value

    def canonical(self, col: str, value: Any, *, side: Literal["source", "target"] = "source") -> str:
        return self._canonical_cell(col, self._preprocess_value(col, value, side=side))

    def _rule_needs_policy_canonical(self, rule: ColumnRule, *, side: Literal["source", "target"]) -> bool:
        if rule.mode != "text" or rule.complex:
            return True
        if side == "source":
            return bool(rule.source_regex_pattern or rule.source_strip_prefix)
        return bool(rule.target_regex_pattern or rule.target_strip_prefix)

    def drilldown_values(
        self,
        record: dict[str, Any],
        key: str,
        *,
        side: Literal["source", "target"],
    ) -> dict[str, str]:
        fm = self.field_for(key)
        if fm is None:
            val = record.get(key)
            return {key: "" if val is None else str(val)}
        physical = fm.source_columns if side == "source" else fm.target_columns
        out: dict[str, str] = {}
        for col in physical:
            val = record.get(col)
            out[col] = "" if val is None else str(val)
        return out

    def field_for(self, key: str) -> FieldMapping | None:
        for fm in self.fields:
            if fm.key == key:
                return fm
        return None

    @classmethod
    def from_mappings(
        cls,
        compare_columns: list[str],
        mappings: list[ColumnMapping] | None,
        *,
        scanned_complex: set[str],
        schema_names: list[str] | None = None,
        uid_column: str = "",
    ) -> ComparePolicy:
        fields = resolve_field_mappings(
            mappings,
            scanned_complex=scanned_complex,
            schema_names=schema_names,
            uid_column=uid_column,
        )
        keys = logical_compare_keys(fields) if fields else compare_columns
        by_src = {
            m.source_column.strip(): m
            for m in (mappings or [])
            if m.source_column and m.source_column.strip()
        }
        rules: dict[str, ColumnRule] = {}
        field_by_key = {f.key: f for f in fields}
        for col in keys:
            fm = field_by_key.get(col)
            m = by_src.get(col)
            if fm is not None:
                rules[col] = ColumnRule(
                    mode=fm.mode,
                    complex=fm.complex,
                    order_sensitive=fm.order_sensitive,
                    target_column=fm.target_columns[0] if fm.target_columns else col,
                    source_columns=fm.source_columns,
                    target_columns=fm.target_columns,
                    source_regex_pattern=m.source_regex_pattern if m else None,
                    source_regex_replacement=m.source_regex_replacement if m else "",
                    target_regex_pattern=m.target_regex_pattern if m else None,
                    target_regex_replacement=m.target_regex_replacement if m else "",
                    source_strip_prefix=m.source_strip_prefix if m else None,
                    target_strip_prefix=m.target_strip_prefix if m else None,
                    is_sensitive=bool(m.is_sensitive) if m else False,
                )
                continue
            if m is None:
                rules[col] = ColumnRule(complex=col in scanned_complex)
                continue
            mode = (m.compare_mode or "auto").lower()
            complex_mode = mode == "structured" or (mode == "auto" and col in scanned_complex)
            tgt = (m.target_column or col).strip() or col
            src_cols = tuple(m.source_columns or ()) or (col,)
            tgt_cols = tuple(m.target_columns or ()) or (tgt,)
            rules[col] = ColumnRule(
                mode=mode,
                complex=complex_mode,
                order_sensitive=m.structured_order_sensitive,
                target_column=tgt,
                source_columns=src_cols,
                target_columns=tgt_cols,
                source_regex_pattern=m.source_regex_pattern,
                source_regex_replacement=m.source_regex_replacement,
                target_regex_pattern=m.target_regex_pattern,
                target_regex_replacement=m.target_regex_replacement,
                source_strip_prefix=m.source_strip_prefix,
                target_strip_prefix=m.target_strip_prefix,
                is_sensitive=bool(m.is_sensitive),
            )
        return cls(rules=rules, fields=fields)


def active_compare_policy() -> ComparePolicy | None:
    return _active.get()


def set_compare_policy(policy: ComparePolicy | None) -> Token:
    return _active.set(policy)


def reset_compare_policy(token: Token) -> None:
    _active.reset(token)


@contextmanager
def compare_policy_context(policy: ComparePolicy | None) -> Iterator[None]:
    token = set_compare_policy(policy)
    try:
        yield
    finally:
        reset_compare_policy(token)


def scan_complex_from_adapters(
    source: Any,
    target: Any,
    mappings: list[ColumnMapping] | None,
    compare_columns: list[str],
    *,
    scan_rows: int = 100,
) -> set[str]:
    found: set[str] = set()
    fields = resolve_field_mappings(mappings, scanned_complex=set())
    src_cols = physical_columns_for_side(fields, "source") if fields else compare_columns
    tgt_cols = physical_columns_for_side(fields, "target") if fields else compare_columns
    for adapter, cols in ((source, src_cols), (target, tgt_cols)):
        n = 0
        for chunk in adapter.stream_records(min(scan_rows, 500)):
            for row in chunk:
                for col in cols:
                    if isinstance(_lit(row.get(col)), _C):
                        for fm in fields:
                            if col in fm.source_columns or col in fm.target_columns:
                                found.add(fm.key)
                                break
                        else:
                            found.add(col)
                n += 1
                if n >= scan_rows:
                    break
            if n >= scan_rows:
                break
    return found


def build_compare_policy(
    source: Any,
    target: Any,
    compare_columns: list[str],
    mappings: list[ColumnMapping] | None,
    *,
    scan_rows: int = 100,
    schema_names: list[str] | None = None,
    uid_column: str = "",
) -> ComparePolicy:
    scanned = scan_complex_from_adapters(
        source,
        target,
        mappings,
        compare_columns,
        scan_rows=scan_rows,
    )
    return ComparePolicy.from_mappings(
        compare_columns,
        mappings,
        scanned_complex=scanned,
        schema_names=schema_names,
        uid_column=uid_column,
    )
