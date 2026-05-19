# Pegasus Backend

A FastAPI-based data validation engine that compares CSV files and generates detailed mismatch reports. The backend provides REST APIs for running validations and retrieving validation results.

## Prerequisites

- **Python**: 3.12 or higher
- **pip**: Package manager for Python
- **PostgreSQL**: 13.0 or higher (for production database)
- **SQLite**: 3.0 or higher (for development/testing)

Verify your Python installation:
```bash
python --version
pip --version
```

## Installation

1. Navigate to the backend directory:
```bash
cd pegasus-backend
```

2. Create a virtual environment:
```bash
python -m venv .venv
```

3. Activate the virtual environment:

**On Linux/macOS:**
```bash
source .venv/bin/activate
```

**On Windows:**
```bash
.venv\Scripts\activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Install development dependencies (optional, for testing and debugging):
```bash
pip install -r requirements-dev.txt
```

## Configuration

The backend uses environment variables for configuration. Create a `.env` file in the `pegasus-backend/` directory:

```bash
# Database
DATABASE_URL=sqlite:///./pegasus.db

# API
API_TITLE=Pegasus API
API_VERSION=1.0.0
LOG_LEVEL=INFO

# CORS (for connecting with frontend)
ALLOWED_ORIGINS=["http://localhost:5173"]
```

For production, use a PostgreSQL connection string:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/pegasus
```

## Running the Project

### Development Mode

Start the development server with auto-reload:

```bash
uvicorn pegasus.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc (ReDoc)

### Production Mode

Run with production settings:

```bash
uvicorn pegasus.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Database Migrations

The backend uses Alembic for database migrations.

### Run Migrations

Apply all pending migrations:
```bash
alembic upgrade head
```

> [!IMPORTANT]
> **Custom Schema Setup (e.g. PostgreSQL with `DB_SCHEMA`):**
> If you are using PostgreSQL and have configured a custom schema (such as `DB_SCHEMA=Pegasus` in your `.env` file), you **must** ensure that the custom schema exists in your PostgreSQL database before running the migrations.
> 
> You can create it by connecting to your database and running:
> ```sql
> CREATE SCHEMA "Pegasus";
> ```
> 
> **Troubleshooting `UndefinedTableError`:**
> If the application fails to start or throws `ProgrammingError: relation "validation_runs" does not exist` when trying to save a validation run, check that:
> 1. You have successfully run `alembic upgrade head` within your virtual environment.
> 2. If using a custom schema, the schema (e.g. `Pegasus`) exists in the database.
> 3. Your database user has sufficient privileges to access and modify the schema.

### Create a New Migration

After modifying models, generate a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Then review the generated file in `alembic/versions/` before running:
```bash
alembic upgrade head
```

### View Migration History

```bash
alembic history
```

## Project Structure

```
pegasus-backend/
├── src/pegasus/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   ├── deps.py             # Dependency injection
│   │   ├── exception_handlers.py # Custom exception handlers
│   │   ├── router.py           # API router registration
│   │   └── v1/
│   │       ├── health.py       # Health check endpoints
│   │       ├── validation.py   # Validation endpoints
│   │       └── router.py       # V1 API router
│   ├── core/
│   │   ├── config.py           # Configuration management
│   │   └── database.py         # Database connection setup
│   ├── models/
│   │   ├── base.py             # SQLAlchemy base model
│   │   ├── enums.py            # Enumeration types
│   │   ├── validation_run.py   # Validation run model
│   │   └── mismatch_report.py  # Mismatch report model
│   ├── schemas/
│   │   ├── health.py           # Health check schemas
│   │   └── validation.py       # Validation request/response schemas
│   ├── services/
│   │   ├── exceptions.py       # Service-level exceptions
│   │   └── validation_service.py # Validation business logic
│   ├── repositories/
│   │   └── validation_repository.py # Data access layer
│   ├── validation/
│   │   ├── engine.py           # Main validation engine
│   │   ├── types.py            # Type definitions
│   │   ├── comparators/        # Comparison logic
│   │   ├── normalizers/        # Data normalization
│   │   ├── parsers/            # File parsing
│   │   ├── readers/            # File reading
│   │   ├── reporters/          # Report generation
│   │   └── uids/               # UID generation
│   └── workers/
├── alembic/                    # Database migration management
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/
│   ├── test_api_validate.py
│   ├── test_polars_csv_reader.py
│   ├── test_sha256_uid_generator.py
│   └── test_uid_based_comparator.py
├── alembic.ini                 # Alembic configuration
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Development dependencies
└── Dockerfile                  # Docker configuration
```

## API Endpoints

### Health Check
- `GET /health` - Check API health status

### Validation Endpoints
- `GET /api/v1/validation/runs` - List all validation runs
- `POST /api/v1/validation/runs` - Create and run a new validation
- `GET /api/v1/validation/runs/{run_id}` - Get specific validation run details
- `GET /api/v1/validation/runs/{run_id}/mismatches` - Get mismatch records for a validation run
   
## Validation Engine Architecture

### Core Components

#### 1. **CSV Reader** (`validation/readers/`)
- **PolarsCSVReader**: Reads CSV files using Polars
- **Auto-Detection**: Supports automatic delimiter detection
- **Handles**: Various encodings, missing columns, data type inference

#### 2. **UID-Based Comparator** (`validation/comparators/uid_based.py`)
- **Main Logic**: 
  ```python
  def compare_dataframes(
      source, target, 
      uid_column="id", 
      compare_columns=["col1", "col2"]
  )
  ```
- **Comparison Operations**:
  1. Anti-join on `uid_column` to find **MISSING_IN_TARGET** rows
  2. Anti-join to find **EXTRA_IN_TARGET** rows
  3. Inner-join + column comparison for **VALUE_MISMATCH** rows

#### 3. **Reconciliation Coordinator** (`validation/reconciliation/coordinator.py`)
- **Orchestrates** strategy selection and execution
- **Selects** best strategy based on:
  - File size vs. memory threshold
  - `assume_sorted` configuration
  - Available disk space
- **Manages** temporary workspace and cleanup

#### 4. **Partition Comparator** (`validation/reconciliation/partition_comparator.py`)
- **Handles** comparison of individual partitions
- **Sub-partitioning**: Optional secondary bucketing for skewed data
- **Sort-Merge**: Compares shards within each partition

#### 5. **External Merge Sort** (`validation/reconciliation/external_merge_sort.py`)
- **For**: Very large unsorted datasets
- **Process**:
  1. Read CSV in chunks
  2. Sort each chunk independently
  3. Spill sorted chunks to disk
  4. Merge sorted chunks during read-back

### Mismatch Detection Logic

#### Finding Missing Rows (ANTI-JOIN)
```sql
-- Illustrative relational SQL
SELECT source.uid
FROM source
ANTI JOIN target ON source.uid = target.uid
```
- Returns UIDs that exist in source but not in target
- Each represents a **MISSING_IN_TARGET** mismatch

#### Finding Extra Rows (ANTI-JOIN)
```sql
-- Illustrative relational SQL
SELECT target.uid
FROM target
ANTI JOIN source ON target.uid = source.uid
```
- Returns UIDs that exist in target but not in source
- Each represents an **EXTRA_IN_TARGET** mismatch

#### Finding Value Mismatches (COLUMN COMPARISON)
```sql
-- Illustrative relational SQL
SELECT source.uid, 'column_name' AS column_name, 
       source.column_name, target.column_name
FROM source
INNER JOIN target ON source.uid = target.uid
WHERE source.column_name IS DISTINCT FROM target.column_name
```
- Finds rows with matching UIDs but differing values
- `IS DISTINCT FROM` handles NULL comparisons correctly
- Each differing column generates a separate **VALUE_MISMATCH** record

### Data Flow Through Pipeline

```
1. ValidationService.validate_csv_pair()
   ├─ Detect delimiter (if auto)
   ├─ Load CSV files (Polars)
   ├─ Select reconciliation strategy (Coordinator)
   └─ Execute comparison

2. ReconciliationCoordinator
   ├─ Check file sizes
   ├─ Decide: In-Memory vs. Disk-Backed
   └─ Route to appropriate engine

3. For Small Files (In-Memory):
   ├─ Load both CSVs into Polars DataFrames
   ├─ Call UIDBasedComparator.compare_dataframes()
   └─ Return MismatchReport

4. For Large Files (Disk-Backed, default ``polars`` backend):
   ├─ Polars hash-partition spill + PartitionComparator
   ├─ Hash-partition or sort files
   ├─ Process partitions sequentially
   ├─ Stream mismatches to NDJSON
   └─ Return MismatchReport with artifact path

5. MismatchReport
   ├─ DataFrame with all mismatches
   ├─ Summary stats (counts by type)
   └─ Optional NDJSON artifact file
```

### Configuration Details

**Reconciliation Strategies** (in `.env`):

```bash
# AUTO: Automatically chooses based on file size
VALIDATION_RECONCILIATION_STRATEGY=auto

# ORDERED_STREAM: For pre-sorted CSV files (fastest if applicable)
VALIDATION_RECONCILIATION_STRATEGY=ordered_stream

# SLIDING_WINDOW: For mostly-sorted files with minor skew
VALIDATION_RECONCILIATION_STRATEGY=sliding_window
VALIDATION_RECONCILIATION_SLIDING_WINDOW=1000

# HASH_PARTITION: For unsorted large files
VALIDATION_RECONCILIATION_STRATEGY=hash_partition
VALIDATION_RECONCILIATION_PARTITION_BUCKETS=64

# EXTERNAL_SORT: For very large unsorted files
VALIDATION_RECONCILIATION_STRATEGY=external_sort
VALIDATION_RECONCILIATION_CHUNK_ROWS=500000
```

**Memory Management**:

```bash
# Trigger external memory strategies at this threshold
VALIDATION_EXTERNAL_MEMORY_THRESHOLD_BYTES=26214400  # 25MB

# Chunk size for reading/spilling (Polars)
VALIDATION_RECONCILIATION_CHUNK_ROWS=500000

# Partition count for hash partitioning
VALIDATION_RECONCILIATION_PARTITION_BUCKETS=64

# Secondary hash buckets for skewed data
VALIDATION_RECONCILIATION_SUB_PARTITION_BUCKETS=1

# Reserve disk space headroom multiplier
VALIDATION_RECONCILIATION_DISK_HEADROOM_MULTIPLIER=2.0
```

**Performance Tuning**:

```bash
# Assume CSVs are sorted by UID (enables faster streaming algorithms)
VALIDATION_RECONCILIATION_ASSUME_SORTED=false

# Enable streaming mismatches to disk (reduce peak memory)
VALIDATION_STREAM_MISMATCHES_TO_DISK=false
```

### Mismatch Report Output

**Structure**:
```python
MismatchReport(
    mismatches: DataFrame[uid, mismatch_type, column_name, source_value, target_value, row_detail],
    summary: {
        "missing_in_target": int,
        "extra_in_target": int,
        "value_mismatch": int
    },
    mismatch_artifact_path: Path (optional NDJSON file)
)
```

**Example NDJSON Output** (`mismatches.ndjson`):
```json
{"uid":"USR001","mismatch_type":"missing_in_target","column_name":null,"source_value":null,"target_value":null,"row_detail":"{\"source_record\":{...},\"target_record\":null}"}
{"uid":"ORD002","mismatch_type":"extra_in_target","column_name":null,"source_value":null,"target_value":null,"row_detail":"{\"source_record\":null,\"target_record\":{...}}"}
{"uid":"INV003","mismatch_type":"value_mismatch","column_name":"amount","source_value":"100.50","target_value":"100.75","row_detail":"{\"source_record\":{...},\"target_record\":{...}}"}
```

## How validation currently works (backend internals)

This section explains the concrete runtime flow implemented in the backend, how jobs are started, monitored, and how results are persisted.

### Job submission paths

- `POST /api/v1/validation/runs` (via uploads) — the API accepts two uploaded CSVs, spools them to a job workspace and starts a worker process.
- `POST /api/v1/validation/local` — the API accepts two local paths (only when enabled) and starts a worker that reads the files in-place.

Both endpoints create a per-job directory under the configured `validation_jobs_directory` (or system temp) and write a `meta.json` and `status.json` file before launching the worker.

### Job workspace layout

Each job runs inside a single directory (`<jobs_root>/<job_id>/`) containing these files:

- `meta.json` — job metadata (uid column, delimiter, run_id, optional source/target paths, upload duration)
- `status.json` — worker progress and human-readable status (updated frequently by the worker)
- `source.csv`, `target.csv` — promoted uploads or pointers to local inputs
- `mismatches.ndjson` — optional mismatch artifact (written when streaming to disk)
- `result.json` — final run summary (counts, artifact filename, durations)
- `worker.log` — combined stdout/stderr and worker logs

The API polls `status.json` to report progress to clients; on completion the API reads `result.json` and builds the API response.

### Worker model and isolation

- The API does not run the heavy reconciliation work in-process. It uses `BackgroundValidationRunner` to either
   - spawn `python -m pegasus.validation.job_worker <job_dir>` as a subprocess, or
   - submit the same entrypoint to a process pool when `validation_worker_pool_size` is configured.
- The worker process creates a `ValidationService` and calls the synchronous validation entrypoint (this avoids asyncio/Polars interop issues inside the web server).
- The worker updates `status.json` periodically via a progress callback; it writes `result.json` and (optionally) `mismatches.ndjson` on success.

### ValidationService behaviour (summary)

- Public entrypoint: `ValidationService.validate_csv_pair()` — runs blocking Polars work on a background thread via `asyncio.to_thread` when invoked from other async code.
- Worker entrypoint uses `ValidationService._validate_csv_pair_sync()` directly for simpler process-local execution.
- Steps performed:
   1. Resolve delimiter (supports `auto`, single-char for Polars, or multi-char via pandas fallback).
   2. Validate that the UID column exists in both inputs.
   3. Build a `ReconciliationRuntimeConfig` (from environment-backed `Settings`) and apply host tuning (CPUs, RAM).
   4. Select a reconciliation path:
       - Multichar streaming hash-partition path (when delimiter is multi-char).
       - External-memory reconciliation (Polars partition spill) when files exceed the external-memory threshold or strategy forces external.
       - In-memory comparator (Polars DataFrames + `UIDBasedComparator`) for small files.
   5. Execute the selected engine (`ReconciliationCoordinator` or `UIDBasedComparator`). Progress events are emitted when available.
   6. Produce a `MismatchReport` and optional `mismatches.ndjson` artifact. Return `ValidationRunResult` with counts and artifact path.

### Job worker lifecycle

- The job worker (`pegasus.validation.job_worker`) does:
   1. Load `meta.json` and initialize logging and optional `MemoryMonitor`.
   2. Instantiate `ValidationService` and call the synchronous validation entrypoint with an internal progress callback.
   3. Write `result.json` containing counts, compared columns, and the relative artifact filename (if any).
   4. Update `status.json` to `completed` or `failed` so the API can pick up final state.

### Persistence and database updates

- If `enable_validation_persistence` is set, the API records run lifecycle into the database:
   - On job enqueue the API calls `ValidationRunRepository.create_running()` which inserts a `ValidationRun` with `status=RUNNING` and returns the `run_id`.
   - After the worker completes, when a client polls the job endpoint the API reads `result.json` and calls `_maybe_persist_completed_job()`.
   - `_maybe_persist_completed_job()` verifies the `ValidationRun` is still `RUNNING` and then invokes `ValidationRunRepository.complete_success()` to update aggregates and insert mismatch rows.

- `ValidationRunRepository.complete_success()` behavior:
   - Marks the `ValidationRun` as `COMPLETED` and writes summary counts (`missing_in_target_count`, `extra_in_target_count`, `value_mismatch_count`, `total_mismatch_records`, `is_match`, `completed_at`, etc.).
   - If a `mismatches.ndjson` artifact exists it is streamed and parsed in batches (default batch size 2,000) and persisted into `mismatch_report` rows.
   - If mismatches are present only in-memory (Polars frame) they are converted to dicts and inserted in batches to avoid OOM.
   - `mark_failed()` is used to mark runs that error while the API or worker is handling them.

### Progress reporting

- The worker emits periodic progress events to `status.json` (percent, phase, counters). The API exposes these via `GET /validate/jobs/{job_id}`.
- The worker throttles writes so small frequent updates do not thrash disk (the internal callback rate is limited).

### Notes, caveats and current limitations

- Multi-character delimiters use a pandas fallback and then convert to Polars. This is slower but required for non-standard separators.
- Duplicate UID detection can cause the run to be rejected with `422 Unprocessable` — this is surfaced by `UIDComparisonError`.
- For very large runs the backend may spill to disk; ensure `validation_reconciliation_temp_dir` has sufficient space and that the process has write permissions.
- The DB persistence path may take significant time for very large mismatch artifacts since every mismatch row is inserted into the database in batches.

## Where to look in the code

- Worker runner: `src/pegasus/validation/job_worker.py`
- Background starter: `src/pegasus/services/background_validation_runner.py`
- Validation orchestration: `src/pegasus/services/validation_service.py`
- Persistence helpers: `src/pegasus/repositories/validation_repository.py`
- Reconciliation coordinator and spill pipeline: `src/pegasus/validation/reconciliation/` (coordinator, partition_comparator, partition_manager, …)

If you'd like, I can also add a small diagram that shows the job workspace lifecycle and the DB persistence path, or generate example `curl` snippets for the validation endpoints.
```

### Error Handling

**Key Exceptions**:
- `CSVFileNotFoundError`: Input file doesn't exist
- `CSVParseError`: Invalid CSV format
- `UIDComparisonError`: Duplicate UIDs found
- `ReconciliationError`: Strategy-specific issues
- `ValidationBadRequestError`: Invalid request parameters

## Running Tests

Run all tests:
```bash
pytest
```

Run specific test file:
```bash
pytest tests/test_api_validate.py -v
```

Run with coverage:
```bash
pytest --cov=pegasus tests/
```

## Key Features

- **CSV Validation**: Compare source and target CSV files
- **Flexible UID Generation**: SHA256-based composite key generation
- **Detailed Mismatch Reporting**: Row-level detail in mismatch records
- **Database Persistence**: Store validation runs and results
- **REST API**: Full REST API for validation operations
- **Async Support**: Asynchronous database operations for better performance

## Development Workflow

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes** and test locally:
   ```bash
   pytest tests/
   ```

3. **Run the development server**:
   ```bash
   uvicorn pegasus.main:app --reload
   ```

4. **Create migrations** if you modified models:
   ```bash
   alembic revision --autogenerate -m "Feature description"
   ```

5. **Commit and push**:
   ```bash
   git add .
   git commit -m "Add feature description"
   git push origin feature/your-feature-name
   ```

## Docker Support

Build the Docker image:
```bash
docker build -t pegasus-backend .
```

Run the container:
```bash
docker run -p 8000:8000 -e DATABASE_URL=sqlite:///./pegasus.db pegasus-backend
```

## Tech Stack

- **FastAPI**: ^0.115.0 - Modern web framework
- **SQLAlchemy**: ^2.0.36 - ORM for database interactions
- **Asyncpg**: ^0.30.0 - Async PostgreSQL driver
- **Alembic**: ^1.14.0 - Database migration tool
- **Polars**: ^1.0.0 - Fast columnar data processing for CSV validation
- **Pydantic**: ^2.10.0 - Data validation and settings management
- **Uvicorn**: ^0.32.0 - ASGI server

## Troubleshooting

### Database Connection Issues
- Ensure PostgreSQL/SQLite is running
- Check `DATABASE_URL` in `.env` file
- Run migrations: `alembic upgrade head`

### Virtual Environment Issues
- Delete `.venv` and recreate it
- Ensure Python 3.12 is used: `python --version`

### Import Errors
- Activate virtual environment: `source .venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`
