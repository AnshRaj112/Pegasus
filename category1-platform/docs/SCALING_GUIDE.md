# Scaling Guide

## Scale Dimensions

| Dimension | Range | Strategy |
|-----------|-------|----------|
| Row count | 100M – 1B | Partitioning + external memory |
| Column count | 100 – 1000+ | Selective compare_columns, column mapping |
| Dataset size | 40GB – 1TB | Disk-backed partitions, object storage |
| Concurrent users | 10 – 100+ | Job isolation, K8s HPA |
| Partitions | 1024 – 8192 | Tunable per dataset size |

## Horizontal Scaling

### Single-Node (Development)
```
1 API pod + inline reconciliation
Memory: 10GB RAM
Throughput: ~1M rows/min (CSV)
```

### Multi-Node (Production)
```
1 API pod (coordinator)
N worker pods (partition processors)
1 Redis (work queue)
S3/MinIO (shared partition storage)
```

### Worker Scaling Formula
```
workers_needed = ceil(active_partitions / partitions_per_worker)
partitions_per_worker = memory_limit_mb / avg_partition_size_mb

Example:
  4096 partitions, 10MB avg partition, 1024MB memory limit
  → partitions_per_worker = 102
  → workers_needed = 40
```

## Vertical Scaling Guidelines

| RAM Available | chunk_size | memory_limit_mb | max_concurrent_partitions |
|--------------|-----------|-----------------|--------------------------|
| 4 GB | 5,000 | 512 | 2 |
| 10 GB | 10,000 | 1,024 | 4 |
| 32 GB | 10,000 | 4,096 | 8 |
| 64 GB | 50,000 | 8,192 | 16 |
| 128 GB | 50,000 | 16,384 | 32 |

## Partition Count Tuning

```
avg_partition_size = dataset_size / num_partitions
target_avg_partition_size = 10MB – 100MB

num_partitions = dataset_size / target_avg_partition_size

Examples:
  10GB dataset  → 1024 partitions → ~10MB each
  80GB dataset  → 4096 partitions → ~20MB each
  250GB dataset → 4096 partitions → ~61MB each
  500GB dataset → 8192 partitions → ~61MB each
```

## Column Count Scaling

For datasets with 1000+ columns:
1. Use `compare_columns` to limit fingerprint scope
2. Use `column_mapping` for heterogeneous schemas
3. Reduce chunk_size to limit per-record memory
4. Enable column drilldown only for flagged records

## Multi-Tenant Scaling

```
Per-tenant isolation:
├── Separate work_dir/{job_id}/
├── Independent memory limits
├── Independent partition counts
└── No shared state

Resource quotas (K8s):
├── memory: 10Gi per worker pod
├── cpu: 4 cores per worker pod
├── ephemeral-storage: 100Gi per worker pod
└── max concurrent jobs: configurable via API rate limit
```

## Network Optimization

For cross-cloud / high-latency environments:
1. **Co-locate workers** with data sources when possible
2. **Use compressed formats** (Parquet over CSV) to reduce transfer
3. **Increase chunk_size** to amortize network round-trips
4. **Parallel partition reads** from object storage
5. **Avoid repeated scans** — partition files cached on local disk

## Storage Scaling

| Dataset Size | Storage Backend | Estimated Disk |
|-------------|----------------|---------------|
| < 10 GB | Local filesystem | 2× dataset size |
| 10–100 GB | Local + spill | 3× dataset size |
| 100–500 GB | S3/MinIO | 2× dataset size |
| 500 GB–1 TB | S3/MinIO + local cache | 1.5× dataset size |

Partition files are deleted on job cleanup.

## Kubernetes HPA Configuration

```yaml
metrics:
  - type: External
    external:
      metric:
        name: category1_queue_depth
      target:
        type: AverageValue
        averageValue: "10"
```

Scale up when queue depth > 10 partitions per worker.
Scale down when queue empty for 5 minutes.

## Bottleneck Analysis

| Bottleneck | Symptom | Resolution |
|-----------|---------|------------|
| Disk I/O | Slow partitioning | NVMe storage, reduce partitions |
| Memory | OOM kills | Reduce chunk_size, lower spill threshold |
| Network | Slow ingestion | Increase chunk_size, co-locate |
| CPU | Slow fingerprinting | More worker pods |
| File count | Slow directory ops | Reduce partition count |
