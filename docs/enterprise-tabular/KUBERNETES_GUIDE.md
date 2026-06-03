# Kubernetes Deployment Guide

## Architecture on Kubernetes

```
┌─────────────────────────────────────────────────┐
│                  Ingress (nginx)               │
│         /api → backend    / → frontend           │
└────────┬──────────────────────┬─────────────────┘
         │                      │
┌────────▼────────┐   ┌────────▼────────┐
│  API Deployment │   │ Frontend Deploy  │
│  (1 replica)    │   │  (2 replicas)    │
└────────┬────────┘   └─────────────────┘
         │
┌────────▼────────┐   ┌─────────────────┐
│ Worker Deploy   │   │  Redis           │
│ (HPA: 2-32)    │◄──│  (work queue)    │
└────────┬────────┘   └─────────────────┘
         │
┌────────▼────────┐
│ MinIO / S3      │
│ (partition store)│
└─────────────────┘
```

## Prerequisites

- Kubernetes 1.25+
- kubectl configured
- Helm 3.x (optional, for Redis)
- StorageClass with ReadWriteMany support (for shared partition storage)

## Quick Deploy

```bash
cd pegasus-backend/deploy/k8s-tabular-workers
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f redis.yaml
kubectl apply -f api-deployment.yaml
kubectl apply -f worker-deployment.yaml
kubectl apply -f frontend-deployment.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml
```

## Resource Requirements

### API Pod
```yaml
resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2
    memory: 4Gi
```

### Worker Pod
```yaml
resources:
  requests:
    cpu: 2
    memory: 4Gi
    ephemeral-storage: 50Gi
  limits:
    cpu: 4
    memory: 10Gi
    ephemeral-storage: 200Gi
```

### Frontend Pod
```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
```

## Horizontal Pod Autoscaler

Workers scale based on Redis queue depth:
```yaml
minReplicas: 2
maxReplicas: 32
metrics:
  - type: External
    external:
      metric:
        name: category1_queue_depth
      target:
        averageValue: "10"
```

Scale-up: queue depth > 10 partitions per worker
Scale-down: queue empty for 300 seconds

## Persistent Storage

For partition files, use a shared PVC:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: category1-work-data
spec:
  accessModes: [ReadWriteMany]
  storageClassName: efs-sc  # or azurefile, gcs-fuse
  resources:
    requests:
      storage: 500Gi
```

For production at scale, use S3-compatible object storage instead:
```yaml
env:
  - name: CATEGORY1_STORAGE_BACKEND
    value: object
  - name: CATEGORY1_OBJECT_STORAGE_BUCKET
    value: category1-partitions
  - name: CATEGORY1_OBJECT_STORAGE_ENDPOINT
    value: http://minio:9000
```

## Worker Execution Model

1. API receives job, creates partition files for source and target
2. API enqueues partition IDs to Redis: `category1:queue:{job_id}`
3. Worker pods dequeue partitions via BLPOP
4. Each worker processes one partition, writes checkpoint
5. When queue empty, API aggregates results and generates report

### Worker Pod Lifecycle
```
Start → Connect Redis → BLPOP partition → Process → Checkpoint → Loop
                                                    ↓ (no work for 30s)
                                                  Exit (HPA scales down)
```

Workers are stateless — any worker can process any partition.

## ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: category1-config
data:
  CATEGORY1_CHUNK_SIZE: "10000"
  CATEGORY1_NUM_PARTITIONS: "4096"
  CATEGORY1_MEMORY_LIMIT_MB: "8192"
  CATEGORY1_SPILL_THRESHOLD_PCT: "0.75"
  CATEGORY1_WORK_DIR: "/data/category1"
  CATEGORY1_MAX_CONCURRENT_PARTITIONS: "4"
  REDIS_URL: "redis://category1-redis:6379/0"
```

## Network Policies

```yaml
# Workers can only reach Redis and object storage
# API can reach all database sources and Redis
# Frontend can only reach API
```

## Monitoring

Recommended Prometheus metrics:
- `category1_jobs_total{status}` — job count by status
- `category1_job_duration_seconds` — job duration histogram
- `category1_partitions_processed_total` — partition throughput
- `category1_memory_peak_mb` — peak memory per job
- `category1_disk_spill_mb` — disk spill volume
- `category1_queue_depth` — Redis queue depth (for HPA)

## Disaster Recovery

| Scenario | Recovery |
|----------|----------|
| Worker pod crash | Partition re-enqueued from checkpoint |
| API pod crash | Jobs in progress resume from partition files |
| Redis crash | Re-enqueue all incomplete partitions |
| Node failure | K8s reschedules pods, workers resume from checkpoints |
| Storage failure | Re-run job from source (source is re-read) |

## Multi-Region Deployment

For cross-region source/target:
1. Deploy workers in each region near data sources
2. Partition locally, transfer partition files to central reconciliation
3. Use object storage replication for partition files
4. Central API coordinates cross-region reconciliation

## Production Checklist

- [ ] Configure Ingress with TLS
- [ ] Set up authentication (OAuth2 proxy or API keys)
- [ ] Configure resource limits on all pods
- [ ] Set up HPA for workers
- [ ] Configure persistent storage or object storage
- [ ] Set up Prometheus monitoring
- [ ] Configure job cleanup cron (delete jobs > 7 days)
- [ ] Network policies for pod isolation
- [ ] Secrets management for database credentials (Vault/Sealed Secrets)
- [ ] Load test with representative dataset sizes
