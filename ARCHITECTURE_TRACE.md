# Architecture Trace (Implementation Path)

**Scope:** Tabular CSV/TSV validation via `pegasus-backend` Category-1 pipeline.

## Entry Points

1. **HTTP API** → `ValidationService._validate_delimited_adapters_sync`
2. **Job worker** → `pegasus.validation.job_worker.run_job_directory` → same service
3. **Benchmarks** → `TabularReconciliationPipeline.run` directly

## Module Map

```
pegasus.services.validation_service
  └─ pegasus.validation.pipeline.pipeline.TabularReconciliationPipeline
       ├─ pegasus.validation.pipeline.in_memory
       ├─ pegasus.validation.pipeline.polars_spill
       ├─ pegasus.validation.pipeline.spill
       ├─ pegasus.validation.pipeline.fingerprint
       ├─ pegasus.validation.pipeline.precheck
       └─ pegasus.validation.adapters.{file_delimited,gcs_delimited,file_columnar}
            └─ pegasus.validation.readers.pyarrow_io
            └─ pegasus.validation.flat_file (multi-char delimiter)
```

## Full Call Sequence (typical local 100K validation)

```
POST /api/v1/validation
  ValidationService._validate_csv_pair_sync
    FileDelimitedAdapter(path, delimiter)
    _validate_delimited_adapters_sync
      resolve_delimiter_for_adapters
      prefetch_gcs_delimited_pair (no-op local)
      compare_columns = schema.columns - uid
      _pipeline_config → TabularPipelineConfig
      TabularReconciliationPipeline.run
        filter_compare_columns(schema, requested)
        should_try_in_memory_reconcile → True (20 MiB < 256 MiB)
        try_in_memory_reconcile
          ThreadPoolExecutor: _load_frame × 2
            _load_delimited_frame
              flat_file.parse_lines (delimiter "||")
              pl.DataFrame(column_data)
          with_columns(_fingerprint_expr)
          anti/inner joins
        PipelineResult
      pipeline_result_to_run_result
```

## Spill Path Sequence (forced disk or large files)

```
TabularReconciliationPipeline.run
  PartitionWriter(source), PartitionWriter(target)
  ThreadPoolExecutor.submit(_partition_side) × 2
    try_partition_side_polars
      _load_frame → Polars DataFrame
      with_columns(identity, fingerprint, canonical cols if drilldown)
      _write_frame_partitions
        partition_by("_pid")
        encode_record / encode_compare_payload_values per row
        PartitionWriter.write_bytes → flush 256 KiB
  list_partition_ids
  for pid in active_pids:
    iter_partition → decode_record
    build src_map / compare fingerprints
    column_comparison on mismatch (if drilldown)
```

## Data Representations by Stage

| Stage | Structure |
|-------|-----------|
| Adapter stream | `list[dict[str, Any]]` per chunk |
| Polars frame | `pl.DataFrame` columnar |
| Spill record | Binary: `>I len | >H key_len | key | 8-byte fp | optional CB01 payload` |
| Reconcile | `dict[str, bytes]` or `dict[str, tuple[bytes, dict]]` |
| API result | `PipelineResult` dataclass → `ValidationRunResult` |

## Configuration Knobs (`Settings` / `TabularPipelineConfig`)

| Setting | Effect |
|---------|--------|
| `validation_auto_in_memory_max_bytes` | Auto Polars join threshold (default 256 MiB) |
| `validation_enable_in_memory_reconcile` | Force in-memory attempt regardless of size |
| `validation_tabular_enable_column_drilldown` | Store compare payloads in spill |
| `force_disk_spill` | Skip in-memory paths |
| `fingerprint_algorithm` | `xxhash64` default |
| `validation_reconciliation_partition_buckets` | Spill partition count |
