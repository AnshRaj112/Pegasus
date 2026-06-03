# Category-1 Reconciliation — Architecture

> **Single product:** Runtime validation and UI are **Pegasus** (`pegasus-backend`, `pegasus-frontend`, root `docker-compose.yml`). This document describes the enterprise tabular reconciliation design; the reference prototype implementation is under `pegasus-backend/reference/category1_engine/`.

## Overview

Category-1 tabular reconciliation is an enterprise-grade approach for validating datasets between Source and Target systems within Pegasus. It performs all heavy computation within its own execution environment, minimizing impact on source systems.

## Design Principles

1. **Source-Safe**: Source systems provide schema, metadata, and streaming records only
2. **Bounded Memory**: Memory usage scales with chunk size, not dataset size
3. **External Memory**: Disk spilling when memory thresholds are reached
4. **Deterministic Partitioning**: Platform-side hashing for reproducible results
5. **Horizontal Scaling**: Stateless workers with partition-level parallelism

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend UI (React)                         │
│              Job Creation │ Progress │ Results │ Reports            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST API
┌──────────────────────────────▼──────────────────────────────────────┐
│                      API Gateway (FastAPI)                          │
│              Job Manager │ Schema Preview │ Report Serving          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                   Reconciliation Engine                             │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ Schema   │  │ Streaming    │  │ Partition   │  │ Mismatch   │ │
│  │ Validator│  │ Partitioner  │  │ Reconciler  │  │ Detector   │ │
│  └──────────┘  └──────────────┘  └─────────────┘  └────────────┘ │
└──────┬─────────────────┬─────────────────┬────────────────────────┘
       │                 │                 │
┌──────▼──────┐  ┌───────▼───────┐  ┌───────▼────────┐
│ Source      │  │ Canonicalizer │  │ Partition      │
│ Adapters    │  │ + Fingerprint │  │ Storage        │
│ (8 DBs +    │  │ Engine        │  │ (Local/S3)     │
│  8 formats) │  │               │  │                │
└─────────────┘  └───────────────┘  └────────────────┘
```

## Component Layers

### Layer 1: Source Adapters
- **Database Adapters**: Teradata, Hive, Oracle, Postgres, SQL Server, Snowflake, BigQuery, Redshift
- **File Readers**: CSV, TSV, PSV, Fixed Width, Parquet, ORC, Avro, Excel
- **Native Columnar Engine** (`readers/native/`): In-house Parquet & ORC parsers — no PyArrow or third-party columnar libraries
- All adapters use streaming cursors/iterators — never load full datasets

### Layer 2: Streaming Reader
- Configurable chunk sizes: 1K, 5K, 10K, 50K rows
- Iterator-based ingestion with backpressure support
- Schema extraction from metadata (no data scan required)

### Layer 3: Canonicalization Engine
- Whitespace trimming, case normalization, null handling
- Decimal precision, date/timestamp/timezone normalization
- Column mapping and type harmonization
- All fingerprinting operates on canonicalized values

### Layer 4: Partition Writer
- Deterministic: `partition_id = HASH(record_identity) % N`
- Hashing performed in platform, NOT in source systems
- Configurable partitions: 1024, 2048, 4096, 8192
- Records written to side-specific partition files on disk

### Layer 5: Distributed Reconciliation Engine
- External hash join per partition
- Disk spilling when memory threshold exceeded (default 75%)
- Merge-join on sorted partition files
- Partition-level parallelism via K8s workers

### Layer 6: Mismatch Detection
- Missing records (in source, not in target)
- Extra records (in target, not in source)
- Changed records (same key, different fingerprint)
- Column-level drilldown for mismatched records only

### Layer 7: Reporting
- VALIDATION_RESULTS.md with full statistics
- Schema differences, sample mismatches, execution metrics
- Memory/disk/network usage tracking

## External Memory Architecture

```
Memory Budget (configurable, e.g. 10GB)
├── In-Memory Hash Buckets (75% threshold)
│   └── Spill to disk when threshold reached
├── Spill Buffer (chunk accumulation)
│   └── JSONL spill files
├── External Hash Table
│   ├── 256 in-memory buckets
│   └── Disk-backed bucket files
└── External Merge Sort
    ├── Sort runs (chunk_size records)
    └── K-way merge for ordered comparison
```

## Data Flow

1. **Schema Validation** — Compare column names, types, nullability, precision (metadata only)
2. **Row Count** — Optional cheap COUNT(*) from metadata
3. **Source Partitioning** — Stream source in chunks → hash → write partition files
4. **Target Partitioning** — Stream target in chunks → hash → write partition files
5. **Partition Reconciliation** — For each partition: build hash table from source, probe with target
6. **Column Drilldown** — For mismatched records only, compare column-by-column
7. **Report Generation** — Aggregate statistics and write VALIDATION_RESULTS.md

## Technology Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI + Uvicorn |
| Frontend | React + TypeScript + Vite |
| Columnar I/O | Native in-house Parquet & ORC readers (`readers/native/`) |
| Avro | fastavro |
| Excel | openpyxl (read-only) |
| Work Queue | Redis |
| Object Storage | S3-compatible (boto3) |
| Container | Docker + Kubernetes |

## Multi-Tenancy

- Job isolation via UUID-scoped work directories
- Configurable memory limits per job
- Independent partition storage per job
- No shared in-memory state between jobs

## Security Considerations

- Credentials passed per-job, never persisted
- Source connections use read-only cursors
- Uploaded files stored in job-scoped directories
- Work directory cleanup on job deletion
