# Category-1 engine reference (not a separate product)

This tree preserves the standalone Category-1 reconciliation prototype (database adapters, native Parquet/ORC readers, external-memory spill, K8s partition workers). It is **not** deployed on its own.

## Canonical product

| Layer | Path |
|-------|------|
| API & job queue | `pegasus-backend/src/pegasus/` |
| Tabular pipeline (production) | `pegasus-backend/src/pegasus/validation/pipeline/` |
| UI | `pegasus-frontend/` |
| Docker | repo root `docker-compose.yml` |

Run Pegasus:

```bash
# From repo root
docker compose up --build

# Or locally
cd pegasus-backend && uvicorn pegasus.main:app --reload --port 8000
cd pegasus-frontend && npm run dev
```

## Using this reference

Port features from `category1/` into `src/pegasus/validation/` as needed (e.g. `core/external_memory.py`, `adapters/database.py`, `readers/fixed_width.py`).

Optional tests (reference package only):

```bash
cd pegasus-backend/reference/category1_engine
pip install -r requirements.txt
PYTHONPATH=. python -m pytest tests/ -v
```

## Related docs

- Enterprise tabular design: `docs/enterprise-tabular/`
- K8s partition workers (future): `pegasus-backend/deploy/k8s-tabular-workers/`
- Production Category-1 pipeline in Pegasus: `docs/CATEGORY1_ARCHITECTURE.md`
