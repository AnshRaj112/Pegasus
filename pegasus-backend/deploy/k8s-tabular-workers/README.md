# Kubernetes — tabular validation workers (optional scale-out)

Manifests for horizontally scaling validation workers backed by Redis.
Workers run `pegasus.validation.distributed_worker_main`, which pulls job
directories from the distributed queue and applies per-job `resource_policy`
stamped in `meta.json` by the API admission governor.

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

See [docs/enterprise-tabular/KUBERNETES_GUIDE.md](../../../docs/enterprise-tabular/KUBERNETES_GUIDE.md).

Set `PEGASUS_VALIDATION_DISTRIBUTED_QUEUE_URL` on API pods to enqueue jobs to Redis;
worker pods consume from the same queue. Resource governor settings in `configmap.yaml`
control auto-tune, utilization slack, and workspace cleanup.
