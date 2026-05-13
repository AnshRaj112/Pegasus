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

#### 4. **DuckDB Reconciliation Engine** (`validation/reconciliation/duckdb_reconciliation_engine.py`)
- **External Memory Joins**: Handles datasets larger than RAM
- **Process**:
  1. Ingest CSVs → optionally convert to Parquet
  2. Partition by `hash(uid) % N`
  3. Run comparison queries per partition
  4. Stream results to NDJSON
- **Key Methods**:
  - `_partition_dup_probe()`: Detect duplicate UIDs
  - `_export_partition_mismatches()`: Generate mismatch records

#### 5. **Partition Comparator** (`validation/reconciliation/partition_comparator.py`)
- **Handles** comparison of individual partitions
- **Sub-partitioning**: Optional secondary bucketing for skewed data
- **Sort-Merge**: Compares shards within each partition

#### 6. **External Merge Sort** (`validation/reconciliation/external_merge_sort.py`)
- **For**: Very large unsorted datasets
- **Process**:
  1. Read CSV in chunks
  2. Sort each chunk independently
  3. Spill sorted chunks to disk
  4. Merge sorted chunks during read-back

### Mismatch Detection Logic

#### Finding Missing Rows (ANTI-JOIN)
```sql
-- DuckDB equivalent
SELECT source.uid
FROM source
ANTI JOIN target ON source.uid = target.uid
```
- Returns UIDs that exist in source but not in target
- Each represents a **MISSING_IN_TARGET** mismatch

#### Finding Extra Rows (ANTI-JOIN)
```sql
-- DuckDB equivalent
SELECT target.uid
FROM target
ANTI JOIN source ON target.uid = source.uid
```
- Returns UIDs that exist in target but not in source
- Each represents an **EXTRA_IN_TARGET** mismatch

#### Finding Value Mismatches (COLUMN COMPARISON)
```sql
-- DuckDB equivalent
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

4. For Large Files (Disk-Backed):
   ├─ DuckDBReconciliationEngine.run()
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

# DuckDB memory limit (ratio of available system memory)
VALIDATION_DUCKDB_MEMORY_LIMIT_RATIO=0.8

# Chunk size for reading/spilling
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

# DuckDB-specific optimizations
VALIDATION_DUCKDB_INGEST_CSV_TO_PARQUET=true
VALIDATION_DUCKDB_PARALLEL_CSV_INGEST=true
VALIDATION_DUCKDB_LOCAL_THREADS=4
VALIDATION_DUCKDB_NETWORK_THREADS=1

# Row group size for Parquet conversion
VALIDATION_DUCKDB_PARQUET_ROW_GROUP_SIZE=65536
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

## Contributing

1. Write clean, readable code following Python conventions
2. Add tests for new features
3. Run tests before committing
4. Keep the README updated
5. Use descriptive commit messages

## License

Proprietary - Pegasus Project
