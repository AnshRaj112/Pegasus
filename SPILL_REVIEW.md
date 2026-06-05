# Spill Review

## Why Spill Exists

- **Memory budget:** Pairs larger than `memory_budget_bytes × 0.65 / 4` cannot hold two full Polars frames.
- **Fingerprint-only reconcile:** Partition files store `(identity, fingerprint)` for anti/extra/changed detection without holding both datasets in RAM simultaneously.
- **Parallel reconcile:** Optional process pool per partition (only when ≥64 active partitions).

## Can Spill Be Avoided?

| Condition | Avoid spill? |
|-----------|--------------|
| Combined size ≤ `validation_auto_in_memory_max_bytes` (256 MiB default) | **Yes** — `in_memory_polars` |
| Identical Merkle / metadata / content digest | **Yes** — precheck exit |
| `force_disk_spill=true` | No |

**Fix (2026-06-04):** Multi-char delimiters now honor auto in-memory size gate.

## Can Spill Be Delayed?

- Lazy column drilldown: fingerprints first; compare columns retained in `DrilldownCache` only when drilldown enabled.
- `fingerprint_only_spill=true` (default): no compare payload in `.bin` files.

## Columnar / Batched / Compressed

| Format | Status |
|--------|--------|
| Per-row JSON | **Removed** from hot path |
| CBL2 columnar batch (`encode_columnar_partition`) | Used when payload required |
| ARW1 Arrow IPC (`encode_arrow_partition_series`) | **Default** fingerprint-only |
| Compression | Not used (CPU tradeoff); candidate: zstd on large partitions |

## Can Spill Be Eliminated?

For Pegasus validation SLOs (&lt;256 MiB pairs, local or cached GCS): **yes — default to in-memory.**  
Spill remains for 1M+ row / wide-column / forced-RAM-limit jobs.

## Spill Pipeline (current)

```
load frame → Polars (_identity, _fp_hash, _pid)
  → partition_by(_pid) batches
  → encode_arrow_partition_series → PartitionWriter buffer
  → flush part_XXXXX.bin
reconcile → read_arrow_partition → Polars join per partition
```

## Recommendations

1. Keep spill as **fallback**, not default for &lt;256 MiB.
2. mmap spill reads for 10M+ row jobs.
3. Do not enable process pool until ≥64 partitions (implemented).
