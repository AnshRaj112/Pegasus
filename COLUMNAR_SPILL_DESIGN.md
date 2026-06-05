# Columnar Spill Design (ARW1)

## Format

```
Repeated blocks in part_NNNNN.bin:

  >I block_len          # length of following body
  ARW1                  # magic (4 bytes)
  Arrow IPC stream      # single RecordBatch
```

## Schema

| Column | Arrow type | Description |
|--------|------------|-------------|
| `identity` | `string` | Canonical identity key (`\|` separated) |
| `fingerprint` | `fixed_size_binary[8]` | Big-endian xxhash64 / Polars hash bytes |

## Write Path

`polars_spill._write_frame_partitions`:

1. `partition_by("_pid")` in Polars  
2. Per bucket: `encode_arrow_partition(identities, hashes)`  
3. `PartitionWriter.write_bytes(pid, block)`  

When drilldown payloads required (legacy eager mode): fall back to **CBL2** (`encode_columnar_partition`) with column-major compare values.

## Read Path

`arrow_spill.read_arrow_partition` → `pl.DataFrame` → `partition_reconcile` joins.

## Properties

| Property | Support |
|----------|---------|
| Sequential write | Append blocks per flush |
| Sequential read | Length-prefixed scan |
| Zero-copy | Arrow buffer → Polars (minimal copy) |
| Batch access | Whole partition as one frame |
| Minimal decode | No per-row Python dict |

## Compatibility

- `iter_partition` still reads CBL2 and legacy length-prefixed records  
- `partition_has_arrow` detects ARW1 for fast path  

## Future

- Parquet row groups per partition for analytics  
- Memory-mapped Arrow IPC for zero-copy reconcile  
- Compressed ZSTD IPC for wide keys  
