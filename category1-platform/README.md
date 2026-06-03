# Category-1 Enterprise Reconciliation Platform

Enterprise-grade tabular data reconciliation platform with external-memory processing, designed for datasets up to 1B rows with minimal source system impact.

## Quick Start

```bash
# Backend
cd category1-platform/backend
pip install -r requirements.txt
uvicorn category1.api.main:app --reload --port 8000

# Frontend (separate terminal)
cd category1-platform/frontend
npm install && npm run dev
```

Open http://localhost:3000 to access the UI.

## Architecture

```
Source Adapter → Streaming Reader → Canonicalization → Partition Writer
  → Distributed Reconciliation Engine → Mismatch Detection → Reporting → Frontend UI
```

All heavy computation (hashing, fingerprinting, partitioning, comparison) runs in the platform — source systems only provide schema, metadata, and streaming records.

## Supported Sources

**Databases**: Teradata, Hive, Oracle, Postgres, SQL Server, Snowflake, BigQuery, Redshift

**File Formats**: CSV, TSV, PSV, Fixed Width, Parquet, ORC, Avro, Excel

## Key Features

- **Bounded memory**: Processing independent of dataset size (chunk + spill model)
- **External memory**: Disk spilling at configurable threshold (default 75%)
- **Deterministic partitioning**: Platform-side hashing, 1024–8192 partitions
- **Column-level drilldown**: Exact column differences for mismatched records
- **Kubernetes-ready**: Stateless workers, checkpointing, HPA scaling
- **Multi-tenant**: Job-isolated work directories and memory limits

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture and component design |
| [CATEGORY1_DESIGN.md](docs/CATEGORY1_DESIGN.md) | Design decisions and trade-offs |
| [RECONCILIATION_FLOW.md](docs/RECONCILIATION_FLOW.md) | End-to-end pipeline flow |
| [SCALING_GUIDE.md](docs/SCALING_GUIDE.md) | Horizontal/vertical scaling guidance |
| [PERFORMANCE_GUIDE.md](docs/PERFORMANCE_GUIDE.md) | Benchmark estimates and tuning |
| [OPERATIONS_GUIDE.md](docs/OPERATIONS_GUIDE.md) | Deployment and operations |
| [KUBERNETES_GUIDE.md](docs/KUBERNETES_GUIDE.md) | K8s deployment guide |

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/jobs` | GET/POST | List/create jobs |
| `/api/jobs/upload` | POST | Create job with file upload |
| `/api/jobs/{id}` | GET/DELETE | Get/delete job |
| `/api/jobs/{id}/report` | GET | Download validation report |

Interactive API docs: http://localhost:8000/docs

## Docker

```bash
cd category1-platform
docker compose up -d
```

## Test

```bash
cd category1-platform/backend
python -m pytest tests/ -v
```
