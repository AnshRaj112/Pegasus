# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T05:05:47Z
# --- END GENERATED FILE METADATA ---

"""Lazy drilldown: columnar frames + batch lookup for mismatch keys only."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any

import polars as pl

DRILLDOWN_SUFFIX = ".ddrill"
DRILLDOWN_LEGACY_SUFFIX = ".ndjsonl"


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

    def persist(self, workspace: Path) -> None:
        """Write source/target drilldown frames for later mismatch NDJSON export."""
        root = Path(workspace)
        root.mkdir(parents=True, exist_ok=True)
        if self._source is not None and not self._source.is_empty():
            self._source.write_parquet(root / "drilldown_source.parquet")
        if self._target is not None and not self._target.is_empty():
            self._target.write_parquet(root / "drilldown_target.parquet")


def load_drilldown_lookup(
    workspace: Path,
    side: str,
    compare_columns: list[str],
    *,
    keys: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Load uid -> column values; when *keys* is set, skip unrelated rows and exit early."""
    root = Path(workspace)
    parquet_path = root / f"drilldown_{side}.parquet"
    if parquet_path.is_file():
        return _load_drilldown_parquet(parquet_path, compare_columns, keys=keys)

    bin_path = root / f"drilldown_{side}{DRILLDOWN_SUFFIX}"
    if bin_path.is_file():
        return _load_drilldown_ddrill(bin_path, compare_columns, keys=keys)

    ndjson_path = root / f"drilldown_{side}{DRILLDOWN_LEGACY_SUFFIX}"
    if ndjson_path.is_file():
        return _load_drilldown_ndjsonl(ndjson_path, compare_columns, keys=keys)
    return {}


def _load_drilldown_parquet(
    path: Path,
    compare_columns: list[str],
    *,
    keys: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    frame = pl.read_parquet(path)
    if frame.is_empty() or "_identity" not in frame.columns:
        return {}
    if keys is not None:
        frame = frame.filter(pl.col("_identity").is_in(list(keys)))
    out: dict[str, dict[str, str]] = {}
    for row in frame.iter_rows(named=True):
        uid = str(row.get("_identity") or "")
        if not uid:
            continue
        out[uid] = {
            col: _as_str(row[col])
            for col in compare_columns
            if col in row
        }
    return out


def _read_u16_be(fp) -> int | None:
    raw = fp.read(2)
    if not raw:
        return None
    if len(raw) < 2:
        raise ValueError("truncated native drilldown record")
    return struct.unpack(">H", raw)[0]


def _load_drilldown_ddrill(
    path: Path,
    compare_columns: list[str],
    *,
    keys: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    need = len(keys) if keys is not None else None
    col_count = len(compare_columns)
    with path.open("rb") as fp:
        while True:
            id_len = _read_u16_be(fp)
            if id_len is None:
                break
            uid_b = fp.read(id_len)
            if len(uid_b) < id_len:
                break
            uid = uid_b.decode("utf-8", errors="replace")
            if keys is None or uid in keys:
                cells: dict[str, str] = {}
                for col in compare_columns:
                    vlen = _read_u16_be(fp)
                    if vlen is None:
                        return out
                    val_b = fp.read(vlen)
                    if len(val_b) < vlen:
                        return out
                    cells[col] = _as_str(val_b.decode("utf-8", errors="replace"))
                out[uid] = cells
                if need is not None and len(out) >= need:
                    return out
            else:
                for _ in range(col_count):
                    vlen = _read_u16_be(fp)
                    if vlen is None:
                        return out
                    fp.seek(vlen, 1)
    return out


def _load_drilldown_ndjsonl(
    path: Path,
    compare_columns: list[str],
    *,
    keys: set[str] | None = None,
) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    need = len(keys) if keys is not None else None
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            uid = str(row.get("_identity") or "")
            if not uid:
                continue
            if keys is not None and uid not in keys:
                continue
            out[uid] = {
                col: _as_str(row[col])
                for col in compare_columns
                if col in row
            }
            if need is not None and len(out) >= need:
                return out
    return out


def _as_str(value: Any) -> str:
    if value is None:
        return "__NULL__"
    return str(value)
