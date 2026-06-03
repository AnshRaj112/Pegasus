# Performance Guide

## Benchmark Estimates (10GB RAM Limit)

All estimates assume:
- 10GB RAM budget (`memory_limit_mb: 10240`)
- chunk_size: 10,000
- num_partitions: 4096
- CSV format, 20 columns, 200 bytes avg row
- Single NVMe node (500 MB/s read, 300 MB/s write)
- Platform-side processing only (files already local)

### 10GB Dataset (~50M rows)

| Metric | Estimate |
|--------|----------|
| Source partitioning | 3.5 min |
| Target partitioning | 3.5 min |
| Partition reconciliation | 4.0 min |
| Column drilldown (1% mismatch) | 0.5 min |
| Report generation | 5 sec |
| **Total wall time** | **~12 min** |
| Peak memory | 2.1 GB |
| Disk spill | 0 MB (fits in memory) |
| Disk usage (partitions) | ~20 GB |
| Partitions with data | ~3,800 |

### 80GB Dataset (~400M rows)

| Metric | Estimate |
|--------|----------|
| Source partitioning | 28 min |
| Target partitioning | 28 min |
| Partition reconciliation | 35 min |
| Column drilldown (1% mismatch) | 4 min |
| Report generation | 15 sec |
| **Total wall time** | **~95 min** |
| Peak memory | 8.5 GB |
| Disk spill | 12 GB |
| Disk usage (partitions) | ~160 GB |
| Partitions with data | ~4,050 |

Memory stays under 10GB via disk spilling at 75% threshold (7.5GB).

### 250GB Dataset (~1.25B rows)

| Metric | Estimate |
|--------|----------|
| Source partitioning | 87 min |
| Target partitioning | 87 min |
| Partition reconciliation | 110 min |
| Column drilldown (0.5% mismatch) | 8 min |
| Report generation | 30 sec |
| **Total wall time** | **~4.8 hours** |
| Peak memory | 9.8 GB |
| Disk spill | 85 GB |
| Disk usage (partitions) | ~500 GB |
| Partitions with data | ~4,096 |

With 4 K8s worker pods (parallel partition reconciliation):
**Estimated wall time: ~1.5 hours**

### 500GB Dataset (~2.5B rows)

| Metric | Estimate |
|--------|----------|
| Source partitioning | 175 min |
| Target partitioning | 175 min |
| Partition reconciliation | 220 min |
| Column drilldown (0.5% mismatch) | 15 min |
| Report generation | 45 sec |
| **Total wall time** | **~9.8 hours** |
| Peak memory | 9.9 GB |
| Disk spill | 180 GB |
| Disk usage (partitions) | ~1 TB |
| Partitions with data | ~4,096 |

With 8 K8s worker pods:
**Estimated wall time: ~3.5 hours**

With 16 K8s worker pods:
**Estimated wall time: ~2.0 hours**

## Performance Tuning

### Chunk Size Impact

| chunk_size | Memory | Throughput | Best For |
|-----------|--------|-----------|----------|
| 1,000 | Low | Lower | Memory-constrained (4GB) |
| 5,000 | Medium | Medium | Balanced |
| 10,000 | Medium | High | Default (10GB+) |
| 50,000 | High | Highest | Wide rows, ample memory |

### Partition Count Impact

| Partitions | File Count | Avg Partition | Reconciliation | Best For |
|-----------|-----------|--------------|----------------|----------|
| 1,024 | 2,048 | ~10 MB | Slower (large) | < 10GB datasets |
| 2,048 | 4,096 | ~5 MB | Medium | 10–50GB |
| 4,096 | 8,192 | ~2.5 MB | Fast | 50–250GB |
| 8,192 | 16,384 | ~1.2 MB | Fastest | 250GB–1TB |

### Format Performance

| Format | Read Speed | Schema Cost | Notes |
|--------|-----------|-------------|-------|
| CSV | 1× (baseline) | Full scan header | Most common |
| TSV/PSV | 1× | Full scan header | Same as CSV |
| Parquet | 3–5× | Metadata only | Best for large datasets |
| ORC | 3–5× | Metadata only | Good compression |
| Avro | 2× | Header schema | Streaming-friendly |
| Excel | 0.3× | First row | Small datasets only |
| Fixed Width | 1.2× | Config required | Legacy systems |

## Memory Independence Proof

Memory consumption formula:
```
peak_memory = chunk_size × avg_row_bytes × overhead_factor
            + hash_bucket_size × avg_entry_bytes
            + spill_buffer_size

Where:
  overhead_factor ≈ 1.5 (Python object overhead)
  hash_bucket_size ≤ max_bucket_size (10,000 entries)
  spill_buffer_size ≤ max_buffer_records (50,000 entries)

With defaults (chunk_size=10000, 200 byte rows):
  peak_memory ≈ 10000 × 200 × 1.5 + 10000 × 500 + 50000 × 500
             ≈ 3MB + 5MB + 25MB = ~33MB per active partition

  With spill at 75% of 10GB = 7.5GB threshold:
    Can hold ~200K hash entries before spill
    Per-partition memory stays bounded regardless of dataset size
```

## Optimization Recommendations

1. **Use Parquet** for datasets > 1GB — 3–5× faster reads, metadata row counts
2. **Set compare_columns** explicitly for wide tables (>100 columns)
3. **Use 8192 partitions** for datasets > 250GB
4. **Deploy workers near data** to minimize network transfer
5. **Use object storage** for partition files in multi-node deployments
6. **Disable row count validation** if source COUNT(*) is expensive
7. **Disable column drilldown** for initial pass, enable for investigation
8. **Set sample_mismatch_limit** to control report size on large mismatch sets

## Monitoring Metrics

| Metric | Alert Threshold |
|--------|----------------|
| peak_memory_mb | > 90% of memory_limit_mb |
| disk_spill_mb | > 50% of available disk |
| partition_processing_time_ms | > 60,000 (1 min) |
| job_duration_seconds | > SLA target |
| spill_file_count | > 100 per partition |
