# Byte Movement Report

**Dataset:** `generated-100k-8cols` (source 11.5 MiB, target 8.3 MiB)  
**Path:** `in_memory_polars` (after optimization)

## Per-Stage Byte Accounting

| Stage | Source Bytes Read | Target Bytes Read | Copied | Serialized | Deserialized | Written | Re-read | Upload | Download |
|-------|-------------------|-------------------|--------|------------|--------------|---------|---------|--------|----------|
| File read (fast multichar) | 11,076,853 | 8,713,127 | 0* | 0 | 0 | 0 | 0 | 0 | 0 |
| Polars DataFrame | (mmap/read into RAM) | same | ~19.8 MiB† | 0 | 0 | 0 | 0 | 0 | 0 |
| Canonical + fingerprint cols | — | — | ~2× compare cols in-engine | 0 | 0 | 0 | 0 | 0 | 0 |
| Join / anti-join | — | — | columnar temps | 0 | 0 | 0 | 0 | 0 | 0 |
| Sample export | — | — | ≤1000 rows dict | minimal JSON | 0 | 0 | 0 | 0 | 0 |
| **Disk spill path** (when forced) | same reads | same | frame → partition groups | Arrow IPC blocks | partition read on reconcile | `part_*.bin` | reconcile read | 0 | 0 |

\* Fast path: single `read_bytes()` per file; no per-row dict.  
† Peak RAM ≈ 2× file size during dual load (ThreadPoolExecutor × 2); released after reconcile.

## Spill Path (`spill_arrow_ipc`, fingerprint-only)

| Stage | Bytes | Justified? |
|-------|-------|------------|
| Input read | ~19.8 MiB | Required once |
| Spill write (source+target) | ~3–6 MiB (identity+fp only) | Only when RAM constrained or `force_disk_spill` |
| Reconcile read | same as spill write | Partition join; could mmap |
| Lazy drilldown cache | ~compare cols × rows in RAM | Only if `enable_column_drilldown`; avoids payload in spill |
| Column payload in spill | 0 (fingerprint-only default) | **Removed** per-row JSON payloads |

## Eliminated Copies (this pass)

| Copy | Before | After |
|------|--------|-------|
| Per-row `dict` in `stream_records` | 100K+ dicts | Not used on auto path |
| `batch_to_dicts` PyArrow | list[dict] per batch | Bypassed for `||` in-memory |
| `to_list()` identity/hash per partition group | Python lists | Arrow Series → IPC where possible |
| Full-file clevercsv→pandas→polars | 2× parse | `load_multichar_csv_fast` |

## Unjustified Copies Still Present (future work)

1. **Dual full-file read** for in-memory (source + target) — acceptable under 256 MiB budget; stream-join for 1–2 GiB pairs.
2. **`read_bytes()` on entire spill file** in `read_arrow_partition` — switch to mmap per partition.
3. **GCS:** download to cache then read again — necessary unless zero-copy mount.
