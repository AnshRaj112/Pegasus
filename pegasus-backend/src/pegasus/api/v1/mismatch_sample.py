# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T05:03:13Z
# --- END GENERATED FILE METADATA ---

"""Stratified sampling of mismatch rows for API responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from pegasus.validation.comparators.models import (
    MISMATCH_REPORT_SCHEMA,
    MismatchType,
    empty_mismatch_frame,
)


def normalize_mismatch_summary(summary: dict[str, Any] | None) -> dict[str, int]:
    """Map pipeline / manifest summary keys to API mismatch type keys."""
    raw = dict(summary or {})
    return {
        MismatchType.MISSING_IN_TARGET.value: int(
            raw.get(
                MismatchType.MISSING_IN_TARGET.value,
                raw.get("missing", raw.get("missing_in_target", 0)),
            )
        ),
        MismatchType.EXTRA_IN_TARGET.value: int(
            raw.get(
                MismatchType.EXTRA_IN_TARGET.value,
                raw.get("extra", raw.get("extra_in_target", 0)),
            )
        ),
        MismatchType.VALUE_MISMATCH.value: int(
            raw.get(
                MismatchType.VALUE_MISMATCH.value,
                raw.get(
                    "changed",
                    raw.get("value_mismatch", raw.get("value_mismatch_records", 0)),
                ),
            )
        ),
    }


def count_mismatch_types_ndjson(path: Path) -> dict[str, int]:
    """Count mismatch rows per category in an NDJSON artifact."""
    counts = {
        MismatchType.MISSING_IN_TARGET.value: 0,
        MismatchType.EXTRA_IN_TARGET.value: 0,
        MismatchType.VALUE_MISMATCH.value: 0,
    }
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            mtype = str(obj.get("mismatch_type") or "")
            if mtype in counts:
                counts[mtype] += 1
    return counts


def reconcile_summary_with_artifact(
    summary: dict[str, Any] | None,
    artifact: Path | None,
) -> dict[str, int]:
    """Prefer the highest per-category count from summary and artifact."""
    merged = normalize_mismatch_summary(summary)
    if artifact is None or not artifact.is_file():
        return merged
    from_file = count_mismatch_types_ndjson(artifact)
    return {
        key: max(int(merged.get(key, 0)), int(from_file.get(key, 0)))
        for key in merged
    }


def load_mismatch_polars_for_api(
    *,
    mismatches: pl.DataFrame,
    mismatch_artifact_path: Path | None,
    n_rows: int | None = None,
) -> pl.DataFrame:
    """Prefer on-disk NDJSON when present; cap rows read so multi-GB mismatch files stay bounded."""
    if mismatch_artifact_path is not None and mismatch_artifact_path.is_file():
        kwargs: dict[str, object] = {"schema": MISMATCH_REPORT_SCHEMA}
        if n_rows is not None:
            kwargs["n_rows"] = n_rows
        return pl.read_ndjson(mismatch_artifact_path, **kwargs)
    return mismatches


def value_mismatch_counts_by_column_ndjson(
    path: Path,
    *,
    max_rows: int | None = None,
) -> dict[str, int]:
    """Stream a mismatch NDJSON file and aggregate value_mismatch rows by column (bounded scan)."""
    counts: dict[str, int] = {}
    vm_seen = 0
    seen_keys: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("mismatch_type") != MismatchType.VALUE_MISMATCH.value:
                continue
            uid = str(obj.get("uid") or "")
            col = obj.get("column_name")
            dedupe_key = (uid, str(col) if col not in (None, "") else "(unknown)")
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            vm_seen += 1
            if max_rows is not None and max_rows > 0 and vm_seen > max_rows:
                return {}
            key = str(col) if col not in (None, "") else "(unknown)"
            counts[key] = counts.get(key, 0) + 1
    return counts


def stratified_value_mismatch_sample(vm: pl.DataFrame, sample_limit: int) -> pl.DataFrame:
    """Mix *value_mismatch* rows across ``column_name`` (round-robin per column).

    *vm* must already be filtered to :data:`MismatchType.VALUE_MISMATCH` rows.
    """
    if sample_limit <= 0 or vm.height == 0:
        return vm.slice(0, 0)
    if vm.height <= sample_limit:
        return vm

    vm_named = vm.filter(pl.col("column_name").is_not_null())
    vm_null = vm.filter(pl.col("column_name").is_null())

    if vm_named.height == 0:
        return vm_null.head(sample_limit)

    unique_cols = sorted(vm_named["column_name"].unique().to_list())
    buckets = {c: vm_named.filter(pl.col("column_name") == c) for c in unique_cols}
    offsets = {c: 0 for c in unique_cols}
    collected: list[pl.DataFrame] = []
    budget = sample_limit

    while budget > 0:
        progressed = False
        for c in unique_cols:
            if budget <= 0:
                break
            b = buckets[c]
            o = offsets[c]
            if o >= b.height:
                continue
            collected.append(b.slice(o, 1))
            offsets[c] = o + 1
            budget -= 1
            progressed = True
        if not progressed:
            break

    if budget > 0 and vm_null.height > 0:
        collected.append(vm_null.head(budget))

    return pl.concat(collected, how="vertical").head(sample_limit)


def allocate_category_sample_limits(n_miss: int, n_ext: int, n_val: int, limit: int) -> tuple[int, int, int]:
    """Split *limit* across three buckets fairly, capped by category sizes.

    When the global budget is at least the number of non-empty categories, each
    non-empty category receives at least one sample row before the remainder is
    spread round-robin. This avoids returning zero *missing* / *extra* samples
    while value mismatches consume the whole budget (which made the detailed UI
    look broken for typical limits like 100).
    """
    if limit <= 0:
        return (0, 0, 0)
    caps = (n_miss, n_ext, n_val)
    total = n_miss + n_ext + n_val
    if total == 0:
        return (0, 0, 0)
    if total <= limit:
        return (n_miss, n_ext, n_val)

    non_empty = [i for i, c in enumerate(caps) if c > 0]
    k = len(non_empty)
    targets = [0, 0, 0]

    if limit >= k:
        for i in non_empty:
            targets[i] = 1
        rem = limit - k
        order = (0, 1, 2)
        while rem > 0:
            progressed = False
            for i in order:
                if rem <= 0:
                    break
                if targets[i] < caps[i]:
                    targets[i] += 1
                    rem -= 1
                    progressed = True
            if not progressed:
                break
        return (targets[0], targets[1], targets[2])

    # Budget smaller than the number of non-empty categories: legacy split.
    base, rem = divmod(limit, 3)
    targets = [
        min(n_miss, base + (1 if rem > 0 else 0)),
        min(n_ext, base + (1 if rem > 1 else 0)),
        min(n_val, base + (1 if rem > 2 else 0)),
    ]
    slack = limit - sum(targets)
    while slack > 0:
        progressed = False
        for j in range(3):
            if targets[j] < caps[j]:
                targets[j] += 1
                slack -= 1
                progressed = True
                if slack <= 0:
                    break
        if not progressed:
            break
    return (targets[0], targets[1], targets[2])


def _empty_sample_frame(mismatches: pl.DataFrame) -> pl.DataFrame:
    if mismatches.height == 0:
        return mismatches.slice(0, 0)
    return pl.DataFrame(schema=mismatches.schema)


def dedupe_value_mismatch_rows(vm: pl.DataFrame) -> pl.DataFrame:
    """Collapse duplicate artifact rows for the same UID/column (legacy double-logging)."""
    if vm.height <= 1:
        return vm
    return vm.unique(subset=["uid", "column_name", "mismatch_type"], keep="first")


def stream_all_value_mismatch_rows_from_ndjson(
    path: Path,
    *,
    n_val: int,
) -> list[dict[str, Any]]:
    """Read every value_mismatch row from the artifact (deduped by uid + column).

    When *n_val* is 0, return every deduped value_mismatch row in the file.
    """
    unlimited = n_val <= 0
    val_lit = MismatchType.VALUE_MISMATCH.value
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("mismatch_type") != val_lit:
                continue
            uid = str(obj.get("uid") or "")
            col = obj.get("column_name")
            dedupe_key = (uid, str(col) if col not in (None, "") else "(unknown)")
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            out.append(obj)
            if not unlimited and len(out) >= n_val:
                break
    return out


def load_value_mismatch_sample_from_ndjson(
    path: Path,
    *,
    n_val: int,
    value_sample_limit: int,
) -> pl.DataFrame:
    """Read up to a bounded prefix of *value_mismatch* lines, then stratify across columns."""
    lv = min(n_val, value_sample_limit) if value_sample_limit > 0 else 0
    if lv <= 0:
        return empty_mismatch_frame()
    # Read enough NDJSON rows to cover all logical mismatches (artifact may over-count).
    read_cap = max(value_sample_limit * 64, 2048, n_val)
    vm_partial = (
        pl.scan_ndjson(str(path), schema=MISMATCH_REPORT_SCHEMA)
        .filter(pl.col("mismatch_type") == pl.lit(MismatchType.VALUE_MISMATCH.value))
        .head(read_cap)
        .collect()
    )
    vm_partial = dedupe_value_mismatch_rows(vm_partial)
    return stratified_value_mismatch_sample(vm_partial, lv)


def paginate_mismatch_rows_from_ndjson(
    path: Path,
    *,
    limit: int,
    offset: int,
    mismatch_type: str | None = None,
    totals_by_type: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return one page of mismatch rows from an NDJSON artifact without loading the full file."""
    totals = normalize_mismatch_summary(totals_by_type)
    if mismatch_type:
        total = int(totals.get(mismatch_type, 0))
    else:
        total = int(sum(totals.values()))

    if total <= 0 or offset >= total:
        return [], total

    items: list[dict[str, Any]] = []
    skipped = 0
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            mtype = str(obj.get("mismatch_type") or "")
            if mismatch_type and mtype != mismatch_type:
                continue
            if skipped < offset:
                skipped += 1
                continue
            items.append(obj)
            if len(items) >= limit:
                break
    return items, total


def stream_presence_mismatch_rows_from_ndjson(
    path: Path,
    *,
    n_miss: int,
    n_ext: int,
    presence_max_rows: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scan the full NDJSON artifact and collect every missing / extra row (capped when *presence_max_rows* > 0)."""
    miss_out: list[dict[str, Any]] = []
    ext_out: list[dict[str, Any]] = []
    miss_cap = n_miss if presence_max_rows <= 0 else min(n_miss, presence_max_rows)
    ext_cap = n_ext if presence_max_rows <= 0 else min(n_ext, presence_max_rows)
    miss_lit = MismatchType.MISSING_IN_TARGET.value
    ext_lit = MismatchType.EXTRA_IN_TARGET.value

    with path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                obj: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                continue
            mt = obj.get("mismatch_type")
            if mt == miss_lit and len(miss_out) < miss_cap:
                miss_out.append(obj)
            elif mt == ext_lit and len(ext_out) < ext_cap:
                ext_out.append(obj)
    return miss_out, ext_out


def build_grouped_mismatch_samples(
    mismatches: pl.DataFrame,
    sample_limit: int,
    *,
    category_counts: tuple[int, int, int] | None = None,
    presence_max_rows: int | None = None,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Return sample frames for missing / extra / value mismatch categories.

    *missing_in_target* and *extra_in_target* include **all** rows from *mismatches* (up to
    *presence_max_rows* per side when that value is > 0). *sample_limit* applies only to
    *value_mismatch* (stratified across ``column_name``).

    When *category_counts* ``(n_missing, n_extra, n_value)`` is provided (typically from
    the report summary), category sizes are taken without three full scans of *mismatches*,
    and samples are built with bounded ``head`` / lazy scans—much cheaper for huge reports.
    """
    empty = _empty_sample_frame(mismatches)
    if mismatches.is_empty():
        return empty, empty, empty

    miss_lit = pl.lit(MismatchType.MISSING_IN_TARGET.value)
    ext_lit = pl.lit(MismatchType.EXTRA_IN_TARGET.value)
    val_lit = pl.lit(MismatchType.VALUE_MISMATCH.value)

    cap = presence_max_rows if presence_max_rows is not None else 0

    if category_counts is None:
        miss = mismatches.filter(pl.col("mismatch_type") == miss_lit)
        ext = mismatches.filter(pl.col("mismatch_type") == ext_lit)
        vm = mismatches.filter(pl.col("mismatch_type") == val_lit)
        lm = miss.height if cap <= 0 else min(miss.height, cap)
        le = ext.height if cap <= 0 else min(ext.height, cap)
        lv = vm.height if sample_limit <= 0 else min(vm.height, sample_limit)
        miss_s = miss.head(lm) if lm else empty
        ext_s = ext.head(le) if le else empty
        if lv and sample_limit <= 0:
            val_s = dedupe_value_mismatch_rows(vm)
        else:
            val_s = stratified_value_mismatch_sample(vm, lv) if lv else empty
        return miss_s, ext_s, val_s

    n_miss, n_ext, n_val = category_counts
    lm = n_miss if cap <= 0 else min(n_miss, cap)
    le = n_ext if cap <= 0 else min(n_ext, cap)
    lv = n_val if sample_limit <= 0 else min(n_val, sample_limit)
    lf = mismatches.lazy()
    miss_s = lf.filter(pl.col("mismatch_type") == miss_lit).head(lm).collect() if lm else empty
    ext_s = lf.filter(pl.col("mismatch_type") == ext_lit).head(le).collect() if le else empty
    if lv > 0:
        if sample_limit <= 0:
            val_s = dedupe_value_mismatch_rows(
                lf.filter(pl.col("mismatch_type") == val_lit).collect(),
            )
        else:
            vm_cap = min(n_val, max(sample_limit * 64, 2048))
            vm_partial = lf.filter(pl.col("mismatch_type") == val_lit).head(vm_cap).collect()
            val_s = stratified_value_mismatch_sample(vm_partial, lv)
    else:
        val_s = empty
    return miss_s, ext_s, val_s


def value_mismatch_counts_by_column(
    mismatches: pl.DataFrame,
    *,
    max_rows: int | None = None,
) -> dict[str, int]:
    """Count value-mismatch rows per compared column (full report, not the sample).

    When *max_rows* is set (>0) and the value-mismatch slice exceeds it, returns an
    empty dict so callers can skip an expensive full scan (see API response flag).
    """
    vm = mismatches.filter(pl.col("mismatch_type") == pl.lit(MismatchType.VALUE_MISMATCH.value))
    if vm.height == 0:
        return {}
    if max_rows is not None and max_rows > 0 and vm.height > max_rows:
        return {}
    keyed = vm.with_columns(
        pl.when(pl.col("column_name").is_null() | (pl.col("column_name") == pl.lit("")))
        .then(pl.lit("(unknown)"))
        .otherwise(pl.col("column_name").cast(pl.String))
        .alias("column_key"),
    )
    agg = keyed.group_by("column_key").agg(pl.len().alias("cnt")).sort("column_key")
    out: dict[str, int] = {}
    for col, cnt in agg.select(["column_key", "cnt"]).iter_rows():
        out[str(col)] = int(cnt)
    return out


def build_stratified_mismatch_sample(mismatches: pl.DataFrame, sample_limit: int) -> pl.DataFrame:
    """Return up to *sample_limit* rows (non-value first, then stratified value rows).

    Kept for callers that expect a single mixed sample list.
    """
    miss_s, ext_s, val_s = build_grouped_mismatch_samples(mismatches, sample_limit)
    parts = [miss_s, ext_s, val_s]
    parts = [p for p in parts if p.height > 0]
    if not parts:
        return mismatches.slice(0, 0)
    return pl.concat(parts, how="vertical").head(sample_limit)
