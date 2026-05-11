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
