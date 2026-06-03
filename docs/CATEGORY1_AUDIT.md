# Category 1 (Tabular Data) — Enterprise Reconciliation Engine Audit

**Date:** 2026-06-03  
**Scope:** Tabular sources only (databases + file formats per spec). JSON/XML/media excluded.

---

## Executive Summary

Pegasus already implements a **production-grade external-memory CSV reconciliation stack** (hash partitions, spill-to-Parquet, streaming mismatches, Merkle precheck). Gaps for enterprise cross-technology reconciliation are:

| Area | Prior state | Post-refactor |
|------|-------------|---------------|
| Source adapters | CSV/GCS/local/columnar files only | `TabularSourceAdapter` + file + 9 DB stubs with push-down SQL |
| Canonicalization | Compare-time rules only | `CanonicalizationEngine` (deterministic pre-fingerprint) |
| Multi-stage pipeline | Implicit in `ValidationService` | Explicit Stages 1–6 in `TabularReconciliationPipeline` |
| Partition presets | 16–4096 (host-capped) | 1024 / 2048 / 4096 / **8192** presets + K8s range assignment |
| Warehouse connectors | UI placeholder | SQL templates; drivers pending |

**Tabular validation:** `ValidationService` routes all CSV/columnar full validation through `run_tabular_validation_sync()` (six-stage pipeline). Legacy `ReconciliationCoordinator` / in-memory `UIDBasedComparator` paths were removed from the service layer (coordinator package remains for tests).

---

## Current Architecture (Pre-Refactor)

### Adapters

| Component | Path | Status |
|-----------|------|--------|
| `PolarsCSVReader` | `validation/readers/polars_csv_reader.py` | Production — streaming batches |
| `StreamCSVReader` | `validation/reconciliation/stream_csv_reader.py` | Facade over Polars |
| `columnar_reader` | `validation/readers/columnar_reader.py` | Parquet/ORC/Avro/Excel — **in-memory** |
| GCS download | `api/v1/validation.py`, `validation/gcs_browse.py` | Production |
| Cloud profiles | `models/cloud_connection.py` | GCS credentials only |
| **Warehouses** | — | **Not implemented** (UI “Soon”) |

### Parsers

| Component | Path | Status |
|-----------|------|--------|
| `FrameParser` (ABC) | `validation/parsers/base.py` | **Stub — no implementations** |
| Delimiter detection | `readers/delimiter_detection.py` | Production |
| File detection pipeline | `validation/file_detection/` | 64 KiB sample classifier |

### Validators

| Component | Path | Role |
|-----------|------|------|
| `csv_preflight` | `validation/csv_preflight.py` | Parseability |
| `mapping_analyze` | `validation/mapping_analyze.py` | Wizard mapping |
| `compare_rules` / `value_compare` | `validation/compare_rules.py`, `value_compare.py` | Cell semantics |
| `UIDBasedComparator` | `validation/comparators/uid_based.py` | In-memory anti-join |
| `ReconciliationCoordinator` | `validation/reconciliation/coordinator.py` | External-memory CSV strategies |

### APIs

| Endpoint | File |
|----------|------|
| `POST /validate/local`, upload, batch | `api/v1/validation.py` |
| Job poll, history, mismatch sample | `validation_history.py`, `mismatch_sample.py` |
| File detect | `GET /validate/local/detect` |

### Services & Workers

| Service | Path |
|---------|------|
| `ValidationService` | `services/validation_service.py` — central orchestration |
| `ValidationJobQueue` | `services/validation_job_queue.py` |
| `job_worker` | `validation/job_worker.py` — subprocess isolation |
| `batch_job_runner` | `validation/batch_job_runner.py` |
| `ValidationEngine` | `validation/engine.py` — was wiring-only stub |

### Reconciliation Flow (Legacy CSV)

```
CSVReader → UID attach → [Merkle precheck] → PartitionManager (hash spill)
    → PartitionComparator (per-bucket sort-merge) → MismatchCollector (NDJSON)
```

---

## Desired vs Actual Pipeline

| Stage | Required | Before | After (new package) |
|-------|----------|--------|---------------------|
| Source Adapter | `get_schema`, `stream_records`, fingerprints | Partial (readers only) | `validation/adapters/` |
| Schema Discovery | Unified | Sample + Polars probe | Stage 1 |
| Canonicalization | Deterministic engine | `value_compare` only | `validation/canonicalization/` |
| Partition Planning | hash(key) % N, 1024–8192 | `uid_partition.py`, max 4096 | Presets + `k8s/partition_assignment.py` |
| Distributed Fingerprinting | Partition summaries only | Merkle (ordered), hash buckets | `fingerprinting/` + Stage 3 |
| Bucket Comparison | Skip matching | Per-bucket compare | Stage 4 |
| Mismatch Detection | Missing/extra/changed | UID comparator | Stage 5 |
| Column Drilldown | Changed rows only | Partial (`row_detail`) | Stage 6 |
| Reporting | VALIDATION_RESULTS.md | API + NDJSON | `pipeline/reporting.py` |

---

## Scalability Review

| Scale | CSV (hash partition path) | Columnar | Database |
|-------|---------------------------|----------|----------|
| **10M rows** | ✅ Designed for | ⚠️ Batched scan; Parquet lazy | 🔶 SQL push-down ready |
| **100M rows** | ✅ With spill + 1M row chunks | ⚠️ Needs external Parquet reconcile | 🔶 Fingerprints at source |
| **500M rows** | ✅ Multi-host K8s partition workers | ❌ Full scan per adapter batch | 🔶 Network = fingerprints only |
| **1B rows** | 🔶 Requires cluster partition farm (8192 buckets × N pods) | ❌ Not yet | ✅ Intended design |

### Findings

1. **100M rows (CSV):** Achievable today with `HASH_PARTITION`, `stream_mismatches`, disk headroom guard. Bottleneck: hot partition RAM in `partition_comparator`.
2. **500M–1B rows:** Requires K8s partition sharding (implemented assignment model), avoid in-memory fallback, increase `partition_buckets` toward 8192.
3. **1000+ columns:** Fingerprint column subset + schema stage; avoid materializing all columns in compare unless mapped.
4. **Columnar at 100M+:** **Primary gap** — legacy path still uses `pl.read_parquet` for small jobs; new `FileColumnarAdapter` uses lazy scan but fingerprint pass still scans full file.

---

## Bottleneck Analysis

### Memory

| Issue | Location | Severity |
|-------|----------|----------|
| Full DataFrame fallback | `validation_service.validate_csv_litmus_sync` | High for large files |
| `pd.read_csv` multichar spill | `partition_manager.spill_multichar_csv_via_polars` | High |
| Columnar full load | `columnar_reader`, `validate_columnar_pair_sync` | High |
| Per-partition `collect()` | `partition_comparator` | Medium (skewed keys) |
| Excel / Avro materialize | `columnar_reader` | High |

### CPU

| Issue | Location |
|-------|----------|
| Duplicate delimiter sniff + preflight + reconcile | Documented in `file-type-detection-architecture.md` |
| Per-row SHA256 in UID generator (Python loop) | `sha256_composite._sha256_hex_series` |
| Repeated hashing | Mitigated in new pipeline (single fingerprint pass per stage) |

### Network

| Issue | Impact |
|-------|--------|
| GCS full download for validate | High egress for large files |
| No warehouse push-down (before) | Would pull entire tables |
| **Mitigation** | DB adapters generate fingerprint SQL only |

### Disk

| Issue | Impact |
|-------|--------|
| Hash partition spill (2× dataset) | Expected; `disk_guard` enforces headroom |
| GNU sort temp files | Very large CSVs |

---

## Refactoring Plan (Completed / Remaining)

### Completed

- [x] `TabularSourceAdapter` contract with push-down capabilities
- [x] `FileDelimitedAdapter`, `FileColumnarAdapter`
- [x] Database stubs + dialect SQL templates (Teradata, Hive, Snowflake, BigQuery, Oracle, SQL Server, PostgreSQL, MySQL, Redshift)
- [x] `SQLAlchemyDatabaseAdapter` (enable with `PEGASUS_USE_SQLALCHEMY_ADAPTERS=true` + driver packages)
- [x] `CanonicalizationEngine` with decimal equivalence option
- [x] `RecordIdentityEngine` (PK, composite, generated, row-hash)
- [x] SHA-256 partition/row fingerprinting + optional HLL precheck (`validation_tabular_enable_hll_precheck`)
- [x] `TabularReconciliationPipeline` (Stages 1–6)
- [x] K8s `assign_partitions()` + env `PEGASUS_WORKER_INDEX` / `PEGASUS_WORKER_COUNT`
- [x] `partition_buckets` max **8192**
- [x] **`ValidationService` + `job_worker` wired** — `validation_tabular_pipeline_enabled=true` (default)
- [x] `POST /api/v1/validate/tabular/pipeline`
- [x] `tabular_integration.py` bridge (Merkle short-circuit, NDJSON mismatches, reports)
- [x] Parquet spill helper `columnar_spill.spill_parquet_to_partitions`
- [x] S3 / Azure browse stubs (`object_storage/s3_browse.py`, `azure_browse.py`)
- [x] `VALIDATION_RESULTS.md` generator per job (`tabular_pipeline_report.md`)

### Operational notes

| Feature | Env var |
|---------|---------|
| SQLAlchemy DB adapters | `PEGASUS_USE_SQLALCHEMY_ADAPTERS=true` |
| K8s partition shard | `PEGASUS_WORKER_INDEX`, `PEGASUS_WORKER_COUNT`, `PEGASUS_PARTITION_COUNT` |
| Partition preset | `PEGASUS_VALIDATION_TABULAR_PARTITION_PRESET` (small/medium/large/xlarge) |

Multichar delimiters use `FileMulticharDelimitedAdapter`. Column mappings / `uid_gte` use `tabular_prepare.prepare_paths_for_pipeline`.

---

## Anti-Pattern Compliance

| Constraint | Status |
|------------|--------|
| No full dataset in memory | ✅ Pipeline design; ⚠️ legacy paths remain |
| No pandas at scale | ✅ Polars streaming; ⚠️ multichar/excel still use pandas |
| No global sort | ✅ Hash partition; per-bucket sort only in legacy comparator |
| No full download (DB) | 🔶 SQL templates; file GCS still downloads |
| No in-memory maps of full dataset | ✅ Partition fingerprints + keyed drilldown |
| No row-by-row network | ✅ Batch iterators; DB push-down |

---

## Key New Modules

```
pegasus/validation/
  adapters/          # TabularSourceAdapter, file + database
  canonicalization/  # Deterministic cell/row canonicalization
  fingerprinting/    # SHA-256 partition/row hashes
  identity/          # Record key strategies
  pipeline/          # Stages 1–6 orchestrator + reporting
  k8s/               # Partition assignment for workers
```

See [CATEGORY1_ARCHITECTURE.md](./CATEGORY1_ARCHITECTURE.md) for diagrams and design decisions.
