# Pegasus Developer Setup & Execution Guide 🚀

Welcome to **Pegasus**! This document provides an end-to-end, step-by-step guide to setting up, configuring, migrating, running, and testing the Pegasus Data Validation & Reconciliation platform from scratch. Whether you are a new developer onboarding to the project or looking to deploy it locally, this guide has everything you need.

## Knowledge Transfer Docs

For the KT-style walkthrough of validations, logic, frontend flows, tests, troubleshooting, FAQ, and onboarding, start here: [KT index](kt/README.md).

---

## 📋 Table of Contents

1. [System Prerequisites](#-system-prerequisites)
2. [Project Architecture & Directory Layout](#-project-architecture--directory-layout)
3. [Quick-Start Dev Setup (PostgreSQL Setup)](#-quick-start-dev-setup-postgresql-setup)
4. [Database Setup & Schema Creation](#-database-setup--schema-creation)
   - [Step A: Create the Database](#step-a-create-the-database)
   - [Step B: Create the Custom Schema (Critical!)](#step-b-create-the-custom-schema-critical)
   - [Step C: Configure Environment Variables](#step-c-configure-environment-variables)
5. [Database Migrations with Alembic](#-database-migrations-with-alembic)
   - [Applying Migrations](#applying-migrations)
   - [Creating a New Migration](#creating-a-new-migration)
   - [Viewing Migration History](#viewing-migration-history)
   - [Understanding the Relational Schema](#understanding-the-relational-schema)
6. [Running the Backend (FastAPI)](#-running-the-backend-fastapi)
7. [Running the Frontend (React + Vite)](#-running-the-frontend-react--vite)
8. [Generating Sample Test Data](#-generating-sample-test-data)
9. [Running Automated Tests](#-running-automated-tests)
10. [🐳 Containerized Setup (Docker)](#-containerized-setup-docker)
11. [⚠️ Troubleshooting & FAQs](#-troubleshooting--faqs)

---

## 🛠️ System Prerequisites

Before you begin, ensure your machine satisfies these environment specifications:

| Technology | Minimum Version | Recommended Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Python** | `3.12` | `3.12.x` | Backend runtime & validation processing engine |
| **Node.js** | `v18.0.0` | `v20.x.x` (LTS) | Frontend runtime environment |
| **npm** | `v9.0.0` | `v10.x.x` | Frontend dependency package manager |
| **PostgreSQL** | `13.0` | `15.0+` | Relational storage for persistent job history & reports |

Verify your system setup by running:
```bash
python --version
node --version
npm --version
```

---

## 🏗️ Project Architecture & Directory Layout

Pegasus is structured as a monorepo consisting of a FastAPI Python backend and a React (Vite) frontend:

```
Pegasus/
├── pegasus-backend/         # FastAPI backend (REST API & reconciliation core)
│   ├── alembic/             # Alembic database migration scripts & versions
│   ├── src/pegasus/         # Core python package source code
│   │   ├── api/             # API routes, dependencies, exception handlers
│   │   ├── core/            # Configuration loaders, DB connectors, resource tuning
│   │   ├── models/          # SQLAlchemy relational models
│   │   ├── repositories/    # Database abstraction layer (repositories)
│   │   ├── services/        # Business logic, job queue, background runner
│   │   └── validation/      # Polars-backed fast CSV reconciliation engines
│   ├── tests/               # Backend Pytest test suite
│   ├── alembic.ini          # Migration configuration
│   ├── requirements.txt     # Main dependencies
│   └── requirements-dev.txt # Dev & testing dependencies
├── pegasus-frontend/        # React + Vite frontend (UI Dashboard)
│   ├── src/                 # React frontend source code
│   │   ├── components/      # UI components (concurrency panel, mismatches, etc.)
│   │   ├── App.jsx          # Route management & dashboard shell
│   │   └── main.jsx         # Application index entry-point
│   └── package.json         # npm dependencies & dev scripts
├── docs/                    # Technical docs & visual flow charts
│   └── diagrams/            # Mermaid diagram source files (.mmd)
├── scripts/                 # Utility scripts (e.g. data generation)
└── test-data/               # Sample CSV datasets
```

---

## 🚀 Quick-Start Dev Setup (PostgreSQL Setup)

To set up Pegasus locally, you will run **PostgreSQL** as the single primary database. Follow these steps:

### 1. Backend Setup
```bash
# Navigate to the backend folder
cd pegasus-backend

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install all packages
pip install -r requirements.txt -r requirements-dev.txt

# Create a local .env file
cp .env.example .env
```
Open `.env` in the `pegasus-backend/` directory and configure your PostgreSQL database connection:
```env
# Define PostgreSQL parameters
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pegasus_db
DB_SCHEMA=Pegasus
PEGASUS_ENABLE_VALIDATION_PERSISTENCE=true
```

Before running migrations, connect to PostgreSQL and create the database and required schema:
```sql
CREATE DATABASE pegasus_db;
\c pegasus_db;
CREATE SCHEMA "Pegasus";
```

Run Alembic migrations to bootstrap the database with tables:
```bash
alembic -c alembic.ini upgrade head
```

Start the FastAPI application:
```bash
uvicorn src.pegasus.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend Setup
Open a new terminal session:
```bash
cd pegasus-frontend
npm install
npm run dev
```

Your browser will launch the frontend dashboard at **`http://localhost:5173`**, pointing seamlessly to your backend API at **`http://localhost:8000`**.

---

## 🗄️ Production Database Setup (PostgreSQL)

When deploying to staging, production, or running multi-user local tests, you should connect Pegasus to a **PostgreSQL** instance. Follow these step-by-step instructions:

### Step A: Create the Database
Connect to your PostgreSQL server using `psql` or an admin tool (e.g., pgAdmin, DBeaver) and create a target database:
```sql
CREATE DATABASE pegasus_db;
```

### Step B: Create the Custom Schema (Critical! ⚠️)

Pegasus relies on isolated schema routing inside PostgreSQL. It routes its persistence model into a custom schema named `"Pegasus"` by default.

> [!IMPORTANT]
> **PostgreSQL does NOT automatically create custom schemas during connection setup.**
> Before running Alembic migrations or launching the backend with a custom schema, you **MUST** connect to your database and execute the following SQL command manually:

```sql
-- Connect to the newly created database
\c pegasus_db;

-- Create the custom schema
CREATE SCHEMA "Pegasus";
```

If you miss this step, Alembic migrations will fail immediately with errors like `ProgrammingError: schema "Pegasus" does not exist`, and any runtime attempts to save validations will fail with `UndefinedTableError: relation "Pegasus.validation_runs" does not exist`.

### Step C: Configure Environment Variables
We support two ways of supplying database connection details:

#### Option 1: Legacy Database Variables (Recommended)
You can define separate connection variables in the `.env` file at the root repository or inside `pegasus-backend/`:
```env
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pegasus_db
DB_SCHEMA=Pegasus
PEGASUS_ENABLE_VALIDATION_PERSISTENCE=true
```
*Note: The Pegasus config engine dynamically joins these components into the required async driver connection URL (`postgresql+asyncpg://...`) behind the scenes.*

#### Option 2: Single Connection URL
Alternatively, export the database URL directly in your process environment or configure it in `.env`:
```env
PEGASUS_DATABASE_URL=postgresql+asyncpg://postgres:your_secure_password@localhost:5432/pegasus_db
PEGASUS_DATABASE_SCHEMA=Pegasus
PEGASUS_ENABLE_VALIDATION_PERSISTENCE=true
```

---

## 🔄 Database Migrations with Alembic

Pegasus uses **Alembic** to manage database schemas. This ensures all team members have consistent database structures.

### Applying Migrations
To bring your database schema completely up to date with the latest code modifications:
1. Ensure your virtual environment is active.
2. Ensure your `.env` contains the correct database credentials.
3. Execute the upgrade command from the `pegasus-backend/` directory:

```bash
alembic -c alembic.ini upgrade head
```

> [!TIP]
> The `-c alembic.ini` argument explicitly tells Alembic to use the configuration file located in the root of the backend folder. Always run this from the `/pegasus-backend` directory.

### Creating a New Migration
If you modify any database models (e.g. in `src/pegasus/models/`):
1. Document the changes in Python (SQLAlchemy structure).
2. Run the Alembic autogenerate command:
   ```bash
   alembic -c alembic.ini revision --autogenerate -m "Add new field to validation runs"
   ```
3. Open the newly created migration file under `alembic/versions/` and inspect the generated SQL-like commands to make sure everything looks correct.
4. Apply the migration:
   ```bash
   alembic -c alembic.ini upgrade head
   ```

### Viewing Migration History
To view the status of applied and pending migrations:
```bash
alembic -c alembic.ini history -v
```

To see the current active database schema version:
```bash
alembic -c alembic.ini current
```

---

### 📊 Understanding the Relational Schema

Pegasus's persistence layer consists of three main structures inside the `"Pegasus"` database schema:

```mermaid
erDiagram
    VALIDATION_RUNS {
        UUID id PK
        VARCHAR status "RUNNING | COMPLETED | FAILED"
        VARCHAR source_filename
        VARCHAR target_filename
        VARCHAR uid_column
        VARCHAR compared_columns
        INTEGER missing_in_target_count
        INTEGER extra_in_target_count
        INTEGER value_mismatch_count
        INTEGER total_mismatch_records
        BOOLEAN is_match
        TIMESTAMP started_at
        TIMESTAMP completed_at
    }

    MISMATCH_REPORTS {
        INTEGER id PK
        UUID run_id FK
        VARCHAR uid
        VARCHAR mismatch_type "missing_in_target | extra_in_target | value_mismatch"
        VARCHAR column_name
        VARCHAR source_value
        VARCHAR target_value
        JSONB row_detail
        TIMESTAMP created_at
    }

    ALEMBIC_VERSION {
        VARCHAR version_num PK
    }

    VALIDATION_RUNS ||--o{ MISMATCH_REPORTS : "has"
```

1. **`validation_runs` Table**: Contains high-level metadata regarding each submitted validation job, including job run durations, configuration, inputs, matching status, and total metrics.
2. **`mismatch_reports` Table**: Holds granular mismatch logs for each run (each missing row, extra row, or value discrepancy creates a record here).
3. **`alembic_version` Table**: Used by Alembic to track migration versions.

---

## 🐍 Running the Backend (FastAPI)

Follow these steps to spin up the backend API locally in development mode:

### 1. Setup Virtual Environment & Install Dependencies
Ensure you are in the `pegasus-backend` directory:
```bash
cd pegasus-backend

# Setup venv
python -m venv .venv
source .venv/bin/activate

# Install dependencies (Main + Development)
pip install -r requirements.txt -r requirements-dev.txt
```

### 2. Configure Environment `.env`
Create a `.env` file using the configuration options outlined in previous sections. A sensible developer config:
```env
PEGASUS_ENVIRONMENT=development
PEGASUS_DEBUG=true

# Database connection settings
PEGASUS_DATABASE_URL=postgresql+asyncpg://postgres:your_secure_password@localhost:5432/pegasus_db
PEGASUS_ENABLE_VALIDATION_PERSISTENCE=true

# Job Queue Settings
PEGASUS_VALIDATION_MAX_CONCURRENCY=2
PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS=true
```

### 3. Launch the Server
Start Uvicorn with live reload:
```bash
uvicorn src.pegasus.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Verify Server Health
Check that the API is up and running by querying these endpoints:
* **Interactive API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Alternative API Docs (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Backend Health Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

---

## ⚛️ Running the Frontend (React + Vite)

Pegasus's frontend UI dashboard is a React application built on Vite.

### 1. Install Node.js Dependencies
Navigate to the `pegasus-frontend/` directory and install dependencies:
```bash
cd pegasus-frontend
npm install
```

### 2. Configure Environment Files
In `pegasus-frontend/`, Vite utilizes `.env.development` to manage connection settings. Ensure it is configured correctly:
```env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Launch Development Server
```bash
npm run dev
```
The application will launch a development server on **`http://localhost:5173`**.

Vite provides hot-module replacement (HMR), meaning any edits you make to React files will immediately render in the browser.

---

## 📂 Generating Sample Test Data

Pegasus features a built-in Python script to generate mock CSV datasets with controllable mismatch profiles (missing keys, extra keys, and distinct column modifications). This is extremely useful for verifying your setup.

To generate sample source and target pairs, run the following script:
```bash
# Ensure you are at the repo root and your virtual env is active
cd /home/ansh.raj/Pegasus

# Run the generator script
python scripts/generate_validation_data.py \
  --rows 50000 \
  --cols 5 \
  --missing 150 \
  --extra 80 \
  --mismatches 300 \
  --output-dir ./test-data
```

This will write three files to the `./test-data/` directory:
1. `source.csv` - The original source dataset.
2. `target.csv` - The modified target dataset containing simulated changes.
3. `expected_mismatches.json` - A ledger of the modifications introduced (to verify engine accuracy).

You can upload these files using the Pegasus frontend to see how the reconciliation engine operates in real-time!

---

## 🧪 Running Automated Tests

Pegasus is backed by an automated test suite.

### Running Backend Tests
Backend tests use `pytest` to exercise the API routes, validation engine, database queries, and repository layers.

To run all tests:
```bash
cd pegasus-backend
pytest
```

To run a specific test suite file with detailed output:
```bash
pytest tests/test_validation_history_api.py -v
```

To measure code coverage:
```bash
pytest --cov=pegasus tests/
```

---

## 🐳 Containerized Setup (Docker)

Run **backend + frontend** from the repository root:

### 1. Create a backend env file
```bash
cp pegasus-backend/.env.example pegasus-backend/.env.backend
# edit pegasus-backend/.env.backend (database, encryption key, etc.)
```

### 2. Start both services
```bash
docker compose up --build
```

- **UI:** http://127.0.0.1:8080 (nginx proxies `/api` to the backend; port 8080 avoids clashing with local Vite on 5173)
- **API:** http://127.0.0.1:8000

Optional helper: `./restart-docker.sh` from the repo root.

For extra host directories (outside `$HOME`), copy `docker-compose.override.example.yml` to `docker-compose.override.yml` and add volume mounts.

---

## ⚠️ Troubleshooting & FAQs

### Q1: I ran Alembic migrations and got `UndefinedTableError` or `ProgrammingError: schema "Pegasus" does not exist`. What did I do wrong?
**Answer**: You did not create the `"Pegasus"` custom database schema in PostgreSQL. Connected to your database engine (using `psql` or an administration GUI) and execute:
```sql
CREATE SCHEMA "Pegasus";
```
Then rerun `alembic -c alembic.ini upgrade head`.

### Q2: I submit a validation but it remains stuck in `QUEUED` state forever.
**Answer**:
1. Check that the Uvicorn server logs aren't displaying exceptions.
2. Ensure the background drain loop is active. The background task is registered on application startup. If you see a database access error in the console immediately on launch, the API might boot but fail to initialize the background queue.
3. If `PEGASUS_ENABLE_VALIDATION_PERSISTENCE` is enabled, check that database migrations have been successfully applied. The background loop polls and updates the job states inside the database.

### Q3: How do I run Pegasus on a machine with very low memory (e.g. 2 GB RAM)?
**Answer**: Adjust these environment variables inside your `.env` file to trigger disk-backed streaming earlier:
```env
# Force Polars disk-spilling comparisons for files larger than 1 MB
PEGASUS_VALIDATION_EXTERNAL_MEMORY_THRESHOLD_BYTES=1048576

# Set maximum parallel validations to 1 (serialize queue execution)
PEGASUS_VALIDATION_MAX_CONCURRENCY=1

# Disable system auto-tuning and stick strictly to 1 job
PEGASUS_VALIDATION_AUTO_TUNE_ENABLED=false
```

### Q4: I get `CORS` blocking errors in my browser console.
**Answer**: Ensure `PEGASUS_CORS_ORIGINS` is configured correctly. In development, if you run the frontend on a non-standard port (e.g. `5174` instead of `5173`), edit your backend `.env` file:
```env
PEGASUS_CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
```
Then restart the backend Uvicorn server.

---

## 🚀 Step-by-Step Onboarding Checklist for New Joiners

Follow this quick checklist to ensure your workspace is ready:
- [ ] Install **Python 3.12+** and **Node.js 18+**.
- [ ] Clone the repository and navigate to `pegasus-backend`.
- [ ] Create `.env` from `.env.example`.
- [ ] Set up the database (If using Postgres, create the `"Pegasus"` schema!).
- [ ] Activate Python virtual environment and run `pip install -r requirements.txt -r requirements-dev.txt`.
- [ ] Run `alembic -c alembic.ini upgrade head` to run migrations.
- [ ] Start the backend: `uvicorn src.pegasus.main:app --reload`.
- [ ] Navigate to `pegasus-frontend` and run `npm install`.
- [ ] Start the frontend: `npm run dev`.
- [ ] Run mock data generator: `python scripts/generate_validation_data.py`.
- [ ] Upload generated `source.csv` and `target.csv` in the UI to run your first validation!
- [ ] Run backend tests with `pytest` to make sure your environment is green.
