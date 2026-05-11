"""Stratified sampling of mismatch rows for API responses."""

from __future__ import annotations

import polars as pl

from pegasus.validation.comparators.models import MismatchType


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


def build_grouped_mismatch_samples(
    mismatches: pl.DataFrame, sample_limit: int
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Return sample frames for missing / extra / value mismatch categories."""
    miss = mismatches.filter(pl.col("mismatch_type") == pl.lit(MismatchType.MISSING_IN_TARGET.value))
    ext = mismatches.filter(pl.col("mismatch_type") == pl.lit(MismatchType.EXTRA_IN_TARGET.value))
    vm = mismatches.filter(pl.col("mismatch_type") == pl.lit(MismatchType.VALUE_MISMATCH.value))

    lm, le, lv = allocate_category_sample_limits(miss.height, ext.height, vm.height, sample_limit)

    miss_s = miss.head(lm) if lm else miss.slice(0, 0)
    ext_s = ext.head(le) if le else ext.slice(0, 0)
    val_s = stratified_value_mismatch_sample(vm, lv) if lv else vm.slice(0, 0)

    return miss_s, ext_s, val_s


def value_mismatch_counts_by_column(mismatches: pl.DataFrame) -> dict[str, int]:
    """Count value-mismatch rows per compared column (full report, not the sample)."""
    vm = mismatches.filter(pl.col("mismatch_type") == pl.lit(MismatchType.VALUE_MISMATCH.value))
    if vm.height == 0:
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
