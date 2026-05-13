# Pegasus

Pegasus is a comprehensive data validation platform that compares CSV files and generates detailed mismatch reports. It consists of a React-based frontend for user interaction and a FastAPI-based backend for validation processing.

## Project Structure

```
Pegasus/
├── pegasus-backend/        # FastAPI backend service
├── pegasus-frontend/       # React + Vite frontend application
├── pegasus-infra/          # Infrastructure and deployment configs
├── benchmarks/             # Performance benchmarks
├── docs/                   # Project documentation
├── test-data/              # Sample test data files
└── scripts/                # Utility scripts
```

## Quick Start

### Prerequisites

- **Node.js**: v18.0.0 or higher
- **Python**: 3.12 or higher
- **npm**: v9.0.0 or higher
- **PostgreSQL** or **SQLite**: For database (SQLite for development)

### Backend Setup

1. Navigate to the backend directory:
```bash
cd pegasus-backend
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file with database configuration:
```bash
DATABASE_URL=sqlite:///./pegasus.db
```

5. Run database migrations:
```bash
alembic upgrade head
```

6. Start the backend server:
```bash
uvicorn pegasus.main:app --reload --host 0.0.0.0 --port 8000
```

Backend API will be available at: `http://localhost:8000`
- **Swagger Documentation**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc

### Frontend Setup

1. Navigate to the frontend directory (in a new terminal):
```bash
cd pegasus-frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

Frontend will be available at: `http://localhost:5173`

## Validation Workflow & Architecture

### Overview

Pegasus compares two CSV files (source and target) by matching rows using a shared **UID (Unique Identifier) column** and reports three types of mismatches:

1. **Missing in Target**: Rows that exist in the source but not in target
2. **Extra in Target**: Rows that exist in the target but not in source  
3. **Value Mismatch**: Rows with matching UIDs but differing column values

### End-to-End Validation Pipeline

```
CSV Files (Source & Target)
    ↓
[Step 1: CSV Reading & Parsing]
    - Read CSV files with auto-detected or specified delimiters
    - Parse data into Polars DataFrames
    ↓
[Step 2: Data Normalization]
    - Convert data types and handle null values
    - Standardize formatting
    ↓
[Step 3: UID-Based Reconciliation]
    - Use shared UID column as join key
    - Select reconciliation strategy based on file size
    ↓
[Step 4: Comparison & Mismatch Detection]
    - Anti-join to find missing/extra rows
    - Semi-join to identify value mismatches
    - Store detailed mismatch records
    ↓
[Step 5: Report Generation]
    - Create structured mismatch report
    - Summary statistics (count of each type)
    - Detailed row-level information for root-cause analysis
    ↓
Mismatch Report (NDJSON + Metrics)
```

### How Mismatches Are Detected

#### 1. Missing in Target (Anti-Join)
- **Logic**: Rows in source but no matching UID in target
- **Detection Method**: Anti-join from source to target on UID column
- **Example**:
  ```
  Source UID=123, Name="Alice"  →  Target has no UID=123  →  MISSING_IN_TARGET
  ```

#### 2. Extra in Target (Anti-Join)
- **Logic**: Rows in target but no matching UID in source
- **Detection Method**: Anti-join from target to source on UID column
- **Example**:
  ```
  Target UID=456, Name="Bob"  →  Source has no UID=456  →  EXTRA_IN_TARGET
  ```

#### 3. Value Mismatch (Semi-Join with Column Comparison)
- **Logic**: Same UID in both but column values differ
- **Detection Method**: 
  - Inner-join on UID to get matching rows
  - Compare each selected column (IS DISTINCT FROM null-aware comparison)
  - Report each mismatched column separately
- **Example**:
  ```
  UID=789 | Source: Age=30, Status="Active"
  UID=789 | Target: Age=31, Status="Active"  →  VALUE_MISMATCH on "Age" column
  ```

### Reconciliation Strategies

Pegasus uses different strategies based on data size and characteristics:

#### 1. **AUTO (Default)**
- Automatically selects best strategy based on:
  - Combined file size vs. memory threshold (default: 25MB)
  - `assume_sorted` configuration
- Recommendation: Use for most cases

#### 2. **ORDERED_STREAM**
- **Prerequisite**: Both CSV files must be globally sorted by UID
- **Method**: Two-pointer merge (like merging sorted linked lists)
- **Memory**: O(batch_size) - very efficient
- **Best For**: Pre-sorted datasets, minimal memory constraints

#### 3. **SLIDING_WINDOW**
- **Prerequisite**: Data mostly sorted by UID (minor skew tolerated)
- **Method**: Like ORDERED_STREAM but maintains sliding window look-ahead
- **Window Size**: Configurable (default: 0 = disabled)
- **Best For**: Nearly-sorted data with occasional out-of-order rows

#### 4. **HASH_PARTITION**
- **Method**: 
  1. Hash each row: `bucket_id = hash(uid) % N` (N = partition_buckets)
  2. Spill rows to disk partitions
  3. Compare each bucket independently
- **Storage**: Temporary disk space for spilled partitions
- **Memory**: Bounded by chunk size and partition count
- **Best For**: Large unsorted datasets, external memory scenarios

#### 5. **EXTERNAL_SORT**
- **Method**:
  1. Sort source and target independently using external merge-sort
  2. Run ORDERED_STREAM on sorted outputs
- **Storage**: Temporary disk space for sorted chunks
- **Best For**: Very large unsorted datasets with stable working directory

### DuckDB Reconciliation Engine

For very large files, Pegasus uses **DuckDB** for efficient external-memory joins:

**Process**:
1. **CSV Ingestion**: Load CSVs into DuckDB (optionally converting to Parquet for speed)
2. **Partitioning**: Partition by UID hash into chunks that fit in memory
3. **Partition Comparison**:
   - For each partition pair (source & target):
     - **Anti-join (Missing)**: `source LEFT ANTI JOIN target ON uid`
     - **Anti-join (Extra)**: `target LEFT ANTI JOIN source ON uid`
     - **Semi-join (Mismatch)**: `source INNER JOIN target ON uid`, then compare columns
4. **Streaming Collection**: Stream mismatches to NDJSON format (avoids full RAM materialization)

**Advantages**:
- Handles 100GB+ files with moderate RAM
- Efficient SQL query optimization
- Disk-backed external joins
- Memory-conscious streaming

### Configuration Parameters

**Key Environment Variables** (in `.env`):

```bash
# Reconciliation strategy
VALIDATION_RECONCILIATION_STRATEGY=auto  # auto|ordered_stream|sliding_window|hash_partition|external_sort

# Memory & Chunk Settings
VALIDATION_RECONCILIATION_CHUNK_ROWS=500000
VALIDATION_EXTERNAL_MEMORY_THRESHOLD_BYTES=26214400  # 25MB

# Partitioning
VALIDATION_RECONCILIATION_PARTITION_BUCKETS=64
VALIDATION_RECONCILIATION_SUB_PARTITION_BUCKETS=1

# Sorting Hints
VALIDATION_RECONCILIATION_ASSUME_SORTED=false
VALIDATION_RECONCILIATION_SLIDING_WINDOW=0

# DuckDB Backend
VALIDATION_RECONCILIATION_BACKEND=duckdb
VALIDATION_DUCKDB_MEMORY_LIMIT_RATIO=0.8
VALIDATION_DUCKDB_INGEST_CSV_TO_PARQUET=true
VALIDATION_DUCKDB_RECONCILIATION_PARTITIONS=32

# Temp Storage
VALIDATION_RECONCILIATION_TEMP_DIR=/tmp/pegasus

# Report Options
VALIDATION_STREAM_MISMATCHES_TO_DISK=false  # Stream instead of materializing
VALIDATION_RECONCILIATION_MISMATCH_NDJSON_MIRROR=false
```

### Mismatch Report Structure

**Output Format**: NDJSON (one JSON object per line) or in-memory DataFrame

**Each Mismatch Record**:
```json
{
  "uid": "12345",
  "mismatch_type": "value_mismatch",
  "column_name": "status",
  "source_value": "ACTIVE",
  "target_value": "INACTIVE",
  "row_detail": "{\"source_record\": {...}, \"target_record\": {...}}"
}
```

**Report Summary**:
```python
{
  "missing_in_target": 145,
  "extra_in_target": 23,
  "value_mismatch": 1087
}
```

### API Endpoint

**POST** `/api/v1/validate`

Request:
```json
{
  "source_path": "/data/source.csv",
  "target_path": "/data/target.csv",
  "uid_column": "customer_id",
  "delimiter": ",",
  "strategy": "auto"
}
```

Response:
```json
{
  "validation_run_id": "uuid-123",
  "source_row_count": 1000000,
  "target_row_count": 998500,
  "compared_columns": ["name", "email", "status"],
  "mismatch_summary": {
    "missing_in_target": 2500,
    "extra_in_target": 0,
    "value_mismatch": 1200
  }
}
```

### Performance Considerations

| Scenario | Recommended Strategy | Memory Need |
|----------|----------------------|------------|
| Small files (<100MB), unsorted | HASH_PARTITION | Low |
| Small files, pre-sorted | ORDERED_STREAM | Very Low |
| Large files (1GB+), unsorted | HASH_PARTITION + DuckDB | Moderate |
| Very large files (100GB+) | EXTERNAL_SORT + DuckDB | Low |
| Streaming ingestion | HASH_PARTITION with mismatch streaming | Low |

### Running Tests

### Backend Tests

```bash
cd pegasus-backend
pytest tests/
```

Run with coverage:
```bash
pytest --cov=pegasus tests/
```

### Frontend Tests (if configured)

```bash
cd pegasus-frontend
npm test
```

## Building for Production

### Backend

```bash
cd pegasus-backend
# Run with production settings
uvicorn pegasus.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Frontend

```bash
cd pegasus-frontend
npm run build
```

Built files will be in `dist/` directory.

## Key Features

### Backend
- ✅ FastAPI REST API for validation operations
- ✅ PostgreSQL/SQLite database support
- ✅ CSV file comparison and validation
- ✅ SHA256-based composite UID generation
- ✅ Detailed mismatch reporting with row-level details
- ✅ Database migrations with Alembic
- ✅ Asynchronous operations for performance
- ✅ Health check endpoints
- ✅ Comprehensive error handling

### Frontend
- ✅ React + Vite modern tech stack
- ✅ Responsive validation panel interface
- ✅ Detailed mismatch record viewing
- ✅ Real-time API communication
- ✅ ESLint code quality checks
- ✅ Hot Module Replacement during development

## API Documentation

### Health Check
```
GET /health
```

### Validation Endpoints
```
GET    /api/v1/validation/runs              # List all validation runs
POST   /api/v1/validation/runs              # Create and run new validation
GET    /api/v1/validation/runs/{run_id}     # Get validation run details
GET    /api/v1/validation/runs/{run_id}/mismatches  # Get mismatch records
```

Refer to the [Backend README](./pegasus-backend/README.md) for detailed API documentation.

## Development Workflow

### Making Changes

1. Create a feature branch:
```bash
git checkout -b feature/your-feature-name
```

2. Make changes and test thoroughly

3. Commit with descriptive messages:
```bash
git add .
git commit -m "Add feature description"
```

4. Push and create a pull request:
```bash
git push origin feature/your-feature-name
```

### Code Quality

- Backend: Follow PEP 8 style guide, write tests, use type hints
- Frontend: Use ESLint rules, keep components modular, test before committing

## Troubleshooting

### Backend Issues
- **Database connection error**: Check `DATABASE_URL` in `.env`
- **Port 8000 already in use**: Change port with `--port 9000`
- **Module import errors**: Activate virtual environment and reinstall dependencies

### Frontend Issues
- **Port 5173 already in use**: Vite will use next available port
- **npm dependencies error**: Delete `node_modules` and `package-lock.json`, then reinstall

### Combined Issues
- Ensure backend is running before starting frontend
- Check CORS settings if API calls fail
- Clear browser cache if frontend doesn't update

## Environment Configuration

### Backend `.env` file

```bash
# Database
DATABASE_URL=sqlite:///./pegasus.db

# API
API_TITLE=Pegasus API
API_VERSION=1.0.0
LOG_LEVEL=INFO

# CORS
ALLOWED_ORIGINS=["http://localhost:5173"]
```

### Frontend Vite Configuration

- Default port: `5173`
- Backend proxy: Configured to forward to `localhost:8000`
- Check `vite.config.js` for details

## Docker Support

### Build Backend Docker Image

```bash
cd pegasus-backend
docker build -t pegasus-backend .
```

### Run Backend Container

```bash
docker run -p 8000:8000 \
  -e DATABASE_URL=sqlite:///./pegasus.db \
  pegasus-backend
```

## Additional Resources

- [Backend README](./pegasus-backend/README.md) - Detailed backend documentation
- [Frontend README](./pegasus-frontend/README.md) - Detailed frontend documentation
- [Test Data](./test-data/) - Sample CSV files for testing; use [scripts/generate_validation_data.py](scripts/generate_validation_data.py) to generate large shuffled source/target pairs with missing, extra, and mismatched rows

## Tech Stack

### Backend
- FastAPI ^0.115.0
- SQLAlchemy ^2.0.36
- Polars ^1.0.0
- Alembic ^1.14.0
- Pydantic ^2.10.0

### Frontend
- React ^19.2.5
- Vite ^8.0.10
- ESLint ^10.2.1

## Contributing

1. Follow the code style guidelines
2. Write tests for new features
3. Keep documentation updated
4. Use meaningful commit messages

## License

Proprietary - Pegasus Project

## Support

For issues, questions, or suggestions, please contact the development team.
