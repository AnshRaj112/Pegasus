# Local Filesystem Analysis

**Date:** 2026-06-04  
**Storage:** Local workspace (SSD class)

## Summary

For the 100K × 8-column (~20.8 MiB) dataset, **CPU-bound parsing and spill serialization dominate**, not disk bandwidth. Local NVMe vs GCS-cached performance is equivalent (~1.7 s in-memory).

## Comparisons

| Path | Local time | GCS (cached mock) | Bottleneck shift |
|------|------------|-------------------|------------------|
| in_memory_polars | 1.7 s | 1.67 s | Parse (flat-file `||`) |
| spill_binary, no drill | 2.9 s | N/A | Serialize + read |
| spill_binary + drill | 6.9 s | N/A | Per-row encode + dict reconcile |

## Disk I/O Profile (spill path)

| Metric | Value |
|--------|-------|
| Flush threshold | 256 KiB per partition |
| Open frequency | Lazy per `part_XXXXX.bin` |
| Typical spill size | Few MiB total (100K rows) |
| Read pattern | Sequential scan per partition file |
| Random I/O | None observed |

## Read Block Sizes

- Full-file read for multi-char delimiter (`_flat_parse_to_polars`)
- PyArrow CSV: 64K default batch for single-byte delimiter streaming
- Partition read: 4-byte length prefix + record body

## CPU / Memory (local)

| Path | Peak RAM | CPU |
|------|----------|-----|
| In-memory | ~40–80 MiB | 1–2 cores during Polars |
| Spill | ~40 MiB + buffers | 2 threads partition + encode |

## vs GCS (uncached)

Not measured live (no bucket in CI). Engineering expectation: uncached GCS adds **RTT + throughput limit** on first read; after prefetch, paths match local.

## Recommendations

1. Use local temp workspace on same volume as spill (`workspace` job dir).
2. Avoid NFS for spill partitions (lock + small-write latency).
3. For &gt;256 MiB files, expect spill — ensure temp dir has 2.5× file size headroom (`disk_headroom_multiplier`).
