# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-05T09:31:09+00:00
# --- END GENERATED FILE METADATA ---

"""Lazy drilldown: columnar frames + batch lookup for mismatch keys only."""

from __future__ import annotations

from typing import Any

import polars as pl


class DrilldownCache:
    """Retains projected compare columns; builds row dicts only for requested keys."""

    __slots__ = ("_source", "_target", "_compare_columns")

    def __init__(self, compare_columns: list[str]) -> None:
        self._compare_columns = list(compare_columns)
        self._source: pl.DataFrame | None = None
        self._target: pl.DataFrame | None = None

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
        if side == "source":
            self._source = subset
        else:
            self._target = subset

    def values_for_keys(self, side: str, keys: list[str]) -> dict[str, dict[str, str]]:
        if not keys:
            return {}
        frame = self._source if side == "source" else self._target
        if frame is None:
            return {}
        str_keys = [str(k) for k in keys]
        filtered = frame.filter(pl.col("_identity").is_in(str_keys))
        if filtered.is_empty():
            return {}
        identities = filtered["_identity"].to_list()
        col_lists = [filtered[c].to_list() for c in self._compare_columns]
        n = len(identities)
        out: dict[str, dict[str, str]] = {}
        for i in range(n):
            key = identities[i]
            if key is None:
                continue
            out[str(key)] = {
                self._compare_columns[j]: _as_str(col_lists[j][i])
                for j in range(len(self._compare_columns))
            }
        return out

    def source_values(self, record_key: str) -> dict[str, str]:
        return self.values_for_keys("source", [record_key]).get(record_key, {})

    def target_values(self, record_key: str) -> dict[str, str]:
        return self.values_for_keys("target", [record_key]).get(record_key, {})


def _as_str(value: Any) -> str:
    if value is None:
        return "__NULL__"
    return str(value)
