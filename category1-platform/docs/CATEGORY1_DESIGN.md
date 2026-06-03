# Category-1 Design Document

## Problem Statement

Enterprise data teams need to validate that datasets migrated or replicated between systems (databases, data lakes, file stores) are consistent. Source systems are often CPU-constrained production environments where heavy computation is prohibited.

## Design Goals

| Goal | Approach |
|------|----------|
| Minimal source impact | Streaming cursors, no hashing/aggregation on source |
| Bounded memory | Chunk-based processing, external memory, disk spilling |
| Extreme scale | 100M–1B rows, 1000+ columns, 40GB–1TB datasets |
| Accuracy | Deterministic partitioning, canonicalization, column drilldown |
| Operability | K8s deployment, checkpointing, retry, horizontal scaling |

## Reconciliation Phases

### Phase 1: Schema Validation
Compare schemas using metadata queries only:
- Column names and ordering
- Data types (with harmonization mapping)
- Nullability constraints
- Numeric precision and scale

**Cost on source**: Single metadata query (negligible)

### Phase 2: Row Count Validation
Optional `COUNT(*)` or metadata-derived row counts.

**Cost on source**: One aggregation query (skippable)

### Phase 3: Streaming Partition Creation
```
FOR each chunk FROM source_reader(chunk_size):
    FOR each record IN chunk:
        identity = canonicalize(key_columns)
        fingerprint = SHA256(canonicalize(compare_columns))
        partition_id = MD5(identity) % num_partitions
        WRITE to partition_file[partition_id]
```

**Memory**: O(chunk_size × record_width)
**Disk**: O(dataset_size) — unavoidable for external-memory reconciliation

### Phase 4: Partition Reconciliation
For each matching partition pair (source, target):
```
BUILD hash_table FROM source_partition (with disk spilling)
FOR each record IN target_partition:
    IF record.key NOT IN hash_table: mark EXTRA
    ELIF record.fingerprint != hash_table[record.key]: mark CHANGED
FOR each key IN hash_table NOT IN target: mark MISSING
```

Uses external hash join — same algorithm as database query optimizers.

### Phase 5: Column-Level Drilldown
Only for records flagged as CHANGED in Phase 4:
```
FOR each compare_column:
    IF canonicalize(source[col]) != canonicalize(target[col]):
        RECORD column difference
```

## Record Identity Strategies

| Strategy | Behavior |
|----------|----------|
| Primary | Use declared primary key columns |
| Composite | Concatenate multiple key columns |
| Business | User-defined business key columns |
| User-defined | Explicit key column list |
| Generated | Hash all columns as identity |
| None | Full-row hash (multiset semantics) |

Duplicate records are handled via multiset semantics — each occurrence is independently fingerprinted.

## Canonicalization Rules

```python
NULL representations: "", "NULL", "null", "None", "NA", "N/A" → __NULL__
Whitespace: configurable trim
Case: configurable sensitivity
Decimals: normalize precision, strip trailing zeros
Dates: normalize to ISO 8601 (YYYY-MM-DD)
Timestamps: normalize to ISO 8601 (YYYY-MM-DDTHH:MM:SS)
Integers: strip commas, normalize
Booleans: true/false normalization
```

## Partitioning Strategy

**Why platform-side hashing?**
- Source systems may prohibit UDFs, hashing functions, or custom SQL
- Deterministic results regardless of source system
- Same partition assignment for source and target enables partition-local comparison

**Partition count selection:**
| Dataset Size | Recommended Partitions |
|-------------|----------------------|
| < 10M rows | 1024 |
| 10M–100M rows | 2048 |
| 100M–500M rows | 4096 |
| 500M–1B rows | 8192 |

Higher partition counts reduce per-partition memory but increase file count and merge overhead.

## Storage Strategy

| Backend | Use Case |
|---------|----------|
| Local filesystem | Development, single-node deployment |
| S3/MinIO | Production K8s, multi-node workers |
| SQLite | Embedded metadata and small partition indexes |

Partition files use a binary format:
```
[4-byte length][JSON payload: {identity_key, fingerprint, raw_data}]
```

## Failure Recovery

- **Checkpointing**: Each partition worker saves state on completion
- **Retry**: Failed partitions re-enqueued via Redis work queue
- **Idempotent**: Re-processing a completed partition returns cached result
- **Job-level**: Source/target partition files persist until job deletion

## Trade-offs

| Decision | Benefit | Cost |
|----------|---------|------|
| External memory vs in-memory | Handles任意 dataset size | Disk I/O overhead |
| Platform-side hashing | Source-safe | Must read all data through platform |
| Partition files vs database | Simple, portable | Many small files at high partition counts |
| SHA256 fingerprints | Collision-resistant | CPU cost per record (acceptable in platform) |
| Sample mismatch limit | Bounded report size | Not all mismatches in report |
