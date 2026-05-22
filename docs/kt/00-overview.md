# Overview

Pegasus is a file validation and reconciliation platform. A user supplies two files, selects a validation mode, and the system compares the source and target data to produce a mismatch report, a validation history record, and dashboard metrics.

## What The Platform Does

- Compares two datasets by a UID or document key.
- Detects missing rows, extra rows, and value mismatches.
- Supports CSV-style delimiter parsing, fixed-width layout analysis, and JSON validation paths.
- Stores validation history so users can revisit prior runs.
- Surfaces the job queue and validation health through the UI.
- Generates sample fixtures through utility scripts for repeatable manual and automated testing.

## Repository Layout In Plain English

- `pegasus-backend/` contains the FastAPI app, validation engine, queueing, persistence, and backend tests.
- `pegasus-frontend/` contains the React UI, API wrappers, dashboard, validation panel, and mapping wizard.
- `scripts/` contains standalone helper programs for fixture generation and one-off validation utilities.
- `docs/` contains the KT pack and the original developer setup guide.
- `test-data/` contains generated or committed fixtures used by validation and benchmarking.

## End-To-End Runtime Flow

1. The frontend gathers file paths, format, UID selection, delimiter, and optional mapping settings.
2. The API receives the request and validates inputs.
3. The backend loads files, resolves delimiters or layouts, and builds comparison rules.
4. The comparison engine runs either directly or through reconciliation workers for large inputs.
5. Mismatch artifacts and summary metadata are returned to the caller and, when enabled, persisted to history.

## Local Run Commands At A Glance

Backend:

```bash
cd pegasus-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic -c alembic.ini upgrade head
uvicorn pegasus.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd pegasus-frontend
npm install
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

Useful validation commands:

```bash
cd pegasus-backend
pytest
pytest tests/test_fixed_width_dates.py

cd ../pegasus-frontend
npm run lint
npm run build
```

## Configuration Keys You Will See Often

- `PEGASUS_DATABASE_URL`: database connection string for PostgreSQL or another supported DB target.
- `PEGASUS_DATABASE_ENCRYPTION_KEY`: required when validation persistence is enabled.
- `PEGASUS_ENABLE_VALIDATION_PERSISTENCE`: turns run history persistence on or off.
- `PEGASUS_CORS_ORIGINS`: comma-separated browser origins when frontend and backend run on different ports.
- `PEGASUS_VALIDATION_MAX_UPLOAD_BYTES`: per-file upload cap.
- `PEGASUS_VALIDATION_MAX_CONCURRENCY`: initial queue concurrency.
- `PEGASUS_VALIDATION_AUTO_TUNE_ENABLED`: whether queue concurrency is automatically reduced under host pressure.

## Validation Modes At A Glance

- CSV / delimiter validation: best fit for standard delimited files and auto-detected delimiters.
- Fixed-width validation: best fit for files with character-based column layouts.
- JSON validation: best fit for document-style records with a document UID.

## What New Engineers Should Remember

- The system is built around the validation service, not around the UI.
- Queue tuning and reconciliation strategy matter for large datasets.
- Most user-visible failures are caused by bad paths, delimiter mismatch, malformed data, or schema/history configuration issues.
- Utility scripts are important because they generate the exact kinds of fixtures used to reproduce edge cases.
