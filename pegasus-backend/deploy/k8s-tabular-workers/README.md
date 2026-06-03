# Kubernetes — tabular partition workers (optional scale-out)

Manifests for horizontally scaling **partition-level** reconciliation workers. They target the reference engine under `pegasus-backend/reference/category1_engine/` until that code is integrated into `src/pegasus/validation/`.

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

**Note:** `worker-deployment.yaml` still invokes the reference `category1` Python package. Build a custom image that includes `reference/category1_engine` or port workers into Pegasus before production use.
