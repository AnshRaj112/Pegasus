# Kubernetes — tabular partition workers (optional scale-out)

Manifests for horizontally scaling **partition-level** reconciliation workers using
`pegasus.validation.workers.partition_worker` and Redis task queues.

## Product stack (default)

Use the repo root Compose file for the full Pegasus app (API + UI):

```bash
docker compose up --build
```

- UI: `http://127.0.0.1:8080` (or `PEGASUS_UI_PORT`)
- API: `http://127.0.0.1:8000` — health at `/api/v1/health`

## Applying these manifests

```bash
kubectl apply -f pegasus-backend/deploy/k8s-tabular-workers/
```

Workers consume partition tasks from Redis (`pegasus:partition_tasks`) and write
results to `pegasus:partition_results:{job_id}`. Spill files must be available on
the shared volume mounted at `PEGASUS_VALIDATION_WORK_DIR`.

Set on the API/coordinator pod when enabling distributed mode:

- `PEGASUS_VALIDATION_DISTRIBUTED_ENABLED=true`
- `PEGASUS_VALIDATION_REDIS_URL=redis://pegasus-redis:6379/0`

See [docs/enterprise-tabular/KUBERNETES_GUIDE.md](../../../docs/enterprise-tabular/KUBERNETES_GUIDE.md).
