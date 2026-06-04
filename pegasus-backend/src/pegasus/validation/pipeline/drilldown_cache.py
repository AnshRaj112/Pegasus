# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-04T12:59:04+05:30
# --- END GENERATED FILE METADATA ---

"""In-memory compare-column lookup for lazy drilldown (avoids spill payloads)."""

from __future__ import annotations

from typing import Any

import polars as pl


class DrilldownCache:
    """Maps identity keys to canonical compare-column values."""

    __slots__ = ("_source", "_target", "_compare_columns")

    def __init__(self, compare_columns: list[str]) -> None:
        self._compare_columns = list(compare_columns)
        self._source: dict[str, dict[str, str]] | None = None
        self._target: dict[str, dict[str, str]] | None = None

    def register_side(
        self,
        side: str,
        frame: pl.DataFrame,
        *,
        identity_column: str = "_identity",
    ) -> None:
        cols = [identity_column, *self._compare_columns]
        missing = [c for c in cols if c not in frame.columns]
        if missing:
            raise ValueError(f"drilldown frame missing columns: {missing}")
        subset = frame.select(cols)
        lookup = _build_lookup(subset, identity_column, self._compare_columns)
        if side == "source":
            self._source = lookup
        else:
            self._target = lookup

    def source_values(self, record_key: str) -> dict[str, str]:
        if self._source is None:
            return {}
        return self._source.get(record_key, {})

    def target_values(self, record_key: str) -> dict[str, str]:
        if self._target is None:
            return {}
        return self._target.get(record_key, {})


def _build_lookup(
    frame: pl.DataFrame,
    identity_column: str,
    compare_columns: list[str],
) -> dict[str, dict[str, str]]:
    identities = frame[identity_column].to_list()
    col_lists = [frame[c].to_list() for c in compare_columns]
    n = len(identities)
    out: dict[str, dict[str, str]] = {}
    for i in range(n):
        key = identities[i]
        if key is None:
            continue
        out[str(key)] = {
            compare_columns[j]: _as_str(col_lists[j][i])
            for j in range(len(compare_columns))
        }
    return out


def _as_str(value: Any) -> str:
    if value is None:
        return "__NULL__"
    return str(value)
