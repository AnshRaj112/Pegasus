# Pegasus API contract (OpenAPI)

The frontend and backend share a single [OpenAPI 3.x](https://swagger.io/specification/) contract in `openapi.yaml`. Any API change must update this file so both sides stay in sync.

## Workflow

1. Change the backend route and/or Pydantic schema in `pegasus-backend`.
2. Regenerate the contract:

   ```bash
   python scripts/sync_openapi_contract.py --write
   ```

3. Update frontend clients in `pegasus-frontend/src/shared/api/` if paths or payloads changed.
4. Run checks locally:

   ```bash
   python scripts/sync_openapi_contract.py --check
   cd pegasus-frontend && npm test -- src/shared/api/tests/contract.test.ts
   ```

CI runs the same checks on pull requests that touch API-related paths.

## What is checked

| Check | Command | Meaning |
|-------|---------|---------|
| Spec validity | `--validate` | `openapi.yaml` is well-formed OpenAPI |
| Backend | `--check-backend` | FastAPI `app.openapi()` matches `api/openapi.yaml` |
| Frontend | `--check-frontend` | `Api.ts` and `adminAuth.ts` only call declared paths/methods |

Placeholder frontend services (`Test.service.ts`, `Setting.service.ts`) are excluded until those routes exist on the backend.

## Interactive docs

When the backend is running, Swagger UI is available at `/docs` and the live spec at `/openapi.json`. The committed `api/openapi.yaml` is the contract of record for CI and code review.

**Docker Compose** (UI on port 8080 by default). Use these URLs **without** `/#/` — hash paths are React app routes, not the API:

- http://127.0.0.1:8080/docs — Swagger UI
- http://127.0.0.1:8080/api/docs — same Swagger UI (under `/api`)
- http://127.0.0.1:8080/openapi.json — live JSON spec
- http://127.0.0.1:8080/api/openapi.json — same JSON spec (under `/api`)

**Direct backend** (port 8000):

- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/openapi.json
