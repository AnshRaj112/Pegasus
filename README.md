# Pegasus

Pegasus is a data validation and reconciliation platform that compares CSV datasets (source vs target), detects row-level mismatches, and provides structured reports for debugging and downstream automation. This repository contains the backend API (FastAPI), a React + Vite frontend UI, migration scripts, sample test data, and utilities to run validations locally or in CI.

## What I changed

- Expanded documentation to cover architecture, deployment, and developer workflows.
- Added Mermaid source diagrams under [docs/diagrams](docs/diagrams) so you can generate images locally.

## Project layout

```
Pegasus/
├── pegasus-backend/        # FastAPI backend service (Python)
├── pegasus-frontend/       # React + Vite frontend (JS/React)
├── docs/                   # Documentation and diagrams
│   └── diagrams/           # Mermaid source files for diagrams
├── test-data/              # Sample CSVs and generated datasets
└── scripts/                # Utility scripts (data generation, helpers)
```

## Quick start (dev)

Backend

```bash
cd pegasus-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # create .env based on example
# set DATABASE_URL in .env (sqlite recommended for quick dev)
alembic -c alembic.ini upgrade head
uvicorn src.pegasus.main:app --reload --host 0.0.0.0 --port 8000
```

Notes:
- API root: http://localhost:8000
- Swagger: http://localhost:8000/docs

Frontend

```bash
cd pegasus-frontend
npm install
npm run dev
```

Notes:
- Frontend dev server default: http://localhost:5173
- Configure the frontend to point to the backend base URL via environment variables in `pegasus-frontend` if needed.

## Architecture (high level)

- The backend exposes REST endpoints (FastAPI) to start and inspect validation runs.
- Validation runs can be executed synchronously or scheduled to background workers.
- The core validation engine reads CSVs into Polars DataFrames, chooses a reconciliation strategy (auto, ordered_stream, sliding_window, hash_partition, external_sort), and streams mismatch results as NDJSON or stores them in the DB for later inspection.
- The frontend provides an interactive UI to submit validation jobs, monitor progress, and inspect mismatch samples.

You can find the Mermaid sources for the architecture and dataflow diagrams here:

- System architecture: [docs/diagrams/system_architecture.mmd](docs/diagrams/system_architecture.mmd)
- Validation dataflow: [docs/diagrams/data_flow.mmd](docs/diagrams/data_flow.mmd)

If you prefer images, install Mermaid CLI and generate SVGs from these sources:

```bash
npm i -g @mermaid-js/mermaid-cli
mmdc -i docs/diagrams/system_architecture.mmd -o docs/diagrams/system_architecture.svg
mmdc -i docs/diagrams/data_flow.mmd -o docs/diagrams/data_flow.svg
```

## Backend: key components

- `src/pegasus/main.py` — FastAPI app entrypoint and router registration.
- `src/pegasus/api/` — API route definitions and dependency wiring.
- `src/pegasus/core/` — configuration, DB connection, helpers.
- `src/pegasus/validation/engine.py` — reconciliation engine core (strategy dispatcher).
- `src/pegasus/services/validation_service.py` — high-level orchestration of validation runs.
- `src/pegasus/models/` — SQLAlchemy models for `ValidationRun`, mismatch reports, and audit tables.
- `alembic/` — migration scripts; use `alembic -c alembic.ini upgrade head` to apply.

Environment variables of interest (set in `.env`):

```bash
# Database
DATABASE_URL=sqlite:///./pegasus.db

# Reconciliation strategy (auto|ordered_stream|sliding_window|hash_partition|external_sort)
VALIDATION_RECONCILIATION_STRATEGY=auto

# Memory & partition tuning
VALIDATION_EXTERNAL_MEMORY_THRESHOLD_BYTES=26214400
VALIDATION_RECONCILIATION_PARTITION_BUCKETS=64
VALIDATION_RECONCILIATION_CHUNK_ROWS=500000
```

## Frontend: key components

- `pegasus-frontend/src/App.jsx` — app shell and routes.
- `pegasus-frontend/src/components/ValidationPanel.jsx` — UI to run and monitor validation jobs.
- `pegasus-frontend/src/components/ValidationMismatchSections.jsx` — mismatch list and details.

Run and develop with HMR using `npm run dev`.

## APIs (common)

- `POST /api/v1/validation/runs` — start a validation job. Payload includes `source_path`, `target_path`, `uid_column`, `delimiter`, `strategy`.
- `GET /api/v1/validation/runs/{id}` — get run metadata and progress.
- `GET /api/v1/validation/runs/{id}/mismatches` — stream or paginate mismatch records.

Refer to the backend code comments for the exact request/response shapes or open the interactive Swagger UI at `/docs`.

## Diagrams included (source)

- [docs/diagrams/system_architecture.mmd](docs/diagrams/system_architecture.mmd) — system components and interactions
- [docs/diagrams/data_flow.mmd](docs/diagrams/data_flow.mmd) — CSV ingestion → reconciliation strategies → mismatch generation

## Running tests

Backend

```bash
cd pegasus-backend
pytest -q
```

Frontend (if configured)

```bash
cd pegasus-frontend
npm test
```

## Troubleshooting & tips

- If migrations fail, ensure `DATABASE_URL` points to a writable DB file and run `alembic -c alembic.ini upgrade head`.
- For very large datasets, increase `VALIDATION_RECONCILIATION_PARTITION_BUCKETS` and ensure `VALIDATION_RECONCILIATION_TEMP_DIR` has enough disk space.
- Use the `test-data/` folder to try small and large generated files before running production workloads.

## Next steps I can take for you

- Generate SVG/PNG images from the Mermaid sources and commit them under `docs/diagrams` (I can do that if you want).
- Add API examples and curl snippets for each endpoint.
- Add CI steps to run backend tests and build frontend on push.

---

If you want me to also generate and commit the rendered diagram SVGs, say "Generate diagrams" and I'll create them and update this README with inline images.
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
