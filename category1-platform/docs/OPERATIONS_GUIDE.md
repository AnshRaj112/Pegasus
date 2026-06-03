# Operations Guide

## Deployment Options

### Local Development
```bash
cd category1-platform/backend
pip install -r requirements.txt
uvicorn category1.api.main:app --reload --port 8000

cd category1-platform/frontend
npm install && npm run dev
```

### Docker Compose
```bash
cd category1-platform
docker compose up -d
```
- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

## Configuration

All settings via environment variables with `CATEGORY1_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| CATEGORY1_CHUNK_SIZE | 10000 | Rows per read chunk |
| CATEGORY1_NUM_PARTITIONS | 4096 | Hash partition count |
| CATEGORY1_MEMORY_LIMIT_MB | 1024 | Memory budget per job |
| CATEGORY1_SPILL_THRESHOLD_PCT | 0.75 | Memory % before disk spill |
| CATEGORY1_WORK_DIR | /tmp/category1 | Working directory |
| CATEGORY1_STORAGE_BACKEND | local | local, object, sqlite |
| CATEGORY1_MAX_CONCURRENT_PARTITIONS | 4 | Parallel partition workers |

## Job Lifecycle

```
PENDING → SCHEMA_VALIDATION → PARTITIONING_SOURCE → PARTITIONING_TARGET
  → RECONCILING → DRILLDOWN → REPORTING → COMPLETED
                                    ↓ (on error)
                                  FAILED
```

### Creating a Job

**Via UI**: Upload source/target files, configure keys, click Start.

**Via API**:
```bash
curl -X POST http://localhost:8000/api/jobs/upload \
  -F "source_file=@source.csv" \
  -F "target_file=@target.csv" \
  -F "key_columns=employee_id" \
  -F "file_format=csv" \
  -F "chunk_size=10000" \
  -F "num_partitions=4096" \
  -F "memory_limit_mb=1024"
```

**Via JSON API** (database sources):
```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "source": {
      "source_type": "postgres",
      "host": "source-db.example.com",
      "database": "analytics",
      "schema_name": "public",
      "table": "employees",
      "credentials": {"user": "reader", "password": "secret"}
    },
    "target": {
      "source_type": "snowflake",
      "database": "DW",
      "schema_name": "PUBLIC",
      "table": "EMPLOYEES",
      "credentials": {"user": "reader", "password": "secret", "account": "xy123"}
    },
    "key_columns": ["employee_id"],
    "chunk_size": 10000,
    "num_partitions": 4096
  }'
```

### Monitoring Jobs

```bash
# List all jobs
curl http://localhost:8000/api/jobs

# Get job status
curl http://localhost:8000/api/jobs/{job_id}/summary

# Get full results
curl http://localhost:8000/api/jobs/{job_id}

# Download report
curl http://localhost:8000/api/jobs/{job_id}/report -o VALIDATION_RESULTS.md
```

### Cleanup

```bash
# Delete job and all associated files
curl -X DELETE http://localhost:8000/api/jobs/{job_id}
```

## Health Checks

```bash
curl http://localhost:8000/api/health
# {"status": "healthy", "version": "1.0.0"}
```

## Disk Management

Partition files accumulate in `{WORK_DIR}/{job_id}/`:
```
{job_id}/
├── source/partitions/part_*.bin
├── target/partitions/part_*.bin
├── spill/part_*/
├── checkpoints/
└── reports/VALIDATION_RESULTS.md
```

**Disk usage**: Approximately 2× combined source + target dataset size.

**Cleanup policy**: Jobs are not auto-deleted. Implement a cron job or lifecycle policy:
```bash
find /data/category1 -maxdepth 1 -mtime +7 -exec rm -rf {} \;
```

## Troubleshooting

| Symptom | Cause | Resolution |
|---------|-------|------------|
| OOM killed | chunk_size too large | Reduce chunk_size or memory_limit_mb |
| Disk full | Large dataset, no cleanup | Delete old jobs, increase disk |
| Slow ingestion | Network latency to source | Co-locate, increase chunk_size |
| Schema mismatch | Different column names/types | Use column_mapping |
| All records mismatched | Wrong key columns | Verify key_columns config |
| High disk spill | Many unique keys per partition | Increase num_partitions |
| Job stuck | Worker crash | Cancel and resubmit |

## Backup and Recovery

- Partition files serve as checkpoint data
- Completed partition checkpoints in `{job_id}/checkpoints/`
- Re-submit failed jobs — completed partitions are skipped
- Reports persisted in `{job_id}/reports/`

## Security Operations

- Rotate database credentials per job (never stored)
- Uploaded files isolated per job UUID
- API has no authentication by default — add reverse proxy auth in production
- Work directory permissions: 700 (owner only)

## Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| CSV | .csv | Configurable delimiter, encoding |
| TSV | .tsv | Tab-delimited |
| PSV | .psv | Pipe-delimited |
| Fixed Width | .txt, .dat | Requires column_specs config |
| Parquet | .parquet | Columnar, metadata row counts |
| ORC | .orc | Columnar, stripe-based |
| Avro | .avro | Schema embedded in file |
| Excel | .xlsx, .xls | Read-only mode, small datasets |

## Supported Database Sources

| Database | Driver | Connection Method |
|----------|--------|------------------|
| PostgreSQL | psycopg2 | host/port/database |
| Oracle | oracledb | DSN or host/port/service |
| SQL Server | pyodbc | ODBC connection string |
| Teradata | teradatasql | host/database |
| Snowflake | snowflake-connector | account/warehouse/database |
| BigQuery | google-cloud-bigquery | project credentials |
| Redshift | redshift-connector | host/port/database |
| Hive | pyhive | host/port/thrift |

All database connections use read-only streaming cursors.
