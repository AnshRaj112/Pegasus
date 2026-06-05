# Lazy Drilldown Design

## Problem

Storing **fingerprint + payload** for every row doubles spill size and forces full-partition payload decode on reconcile. Building a full `dict[key][col]` drilldown cache is O(dataset) RAM.

## Two-Pass Model

### Pass 1 — Fingerprint reconcile

- Spill: `identity` + `fingerprint` only (`fingerprint_only_spill=True`)  
- Reconcile: Polars `inner` + filter `_fp != _fp_tgt`  
- Output: counts + list of **changed keys** (capped at sample limit)

### Pass 2 — Targeted payload fetch

Only for keys in `changed_keys`:

```python
drilldown_cache.values_for_keys("source", changed_keys)
drilldown_cache.values_for_keys("target", changed_keys)
```

## DrilldownCache

| Field | Type | Scope |
|-------|------|-------|
| `_source` | `pl.DataFrame` | Projected: `_identity` + compare columns |
| `_target` | `pl.DataFrame` | Same |

Registration occurs during Polars spill (`register_side`) — frames already in memory from load.

Lookup:

```python
filtered = frame.filter(pl.col("_identity").is_in(str_keys))
# Build dict only for len(changed_keys) rows
```

## Flow

```
Fingerprint Compare (Polars join)
  → Mismatch Detection (anti + inner filter)
  → Targeted Payload Fetch (values_for_keys)
  → Column-Level Diff (per compare column)
```

## Config

| Flag | Default | Effect |
|------|---------|--------|
| `fingerprint_only_spill` | `True` | No payload in spill files |
| `lazy_column_drilldown` | `True` | Use DrilldownCache vs spill payload |
| `enable_column_drilldown` | `True` | Enable Pass 2 |

## Limits

- Drilldown cache still holds full projected frames when Polars load path is used — acceptable under `polars_spill_max_bytes` (256 MiB default)  
- Streaming fallback: no cache → column diffs only if spill payload embedded (eager mode)  

## Future

- Re-read source row by key from streaming adapter (no full-frame cache)  
- Columnar payload sidecar file written only for mismatch partitions  
