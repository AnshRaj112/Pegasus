# File Type Detection — Audit & Upgrade (2026-06-03)

## Pre-upgrade state

| Area | Finding |
|------|---------|
| Detection package | Documented in `file-type-detection-architecture.md` but **not implemented** |
| Runtime routing | `infer_file_format_from_path()` — extension suffix map only |
| Magic / MIME | `python-magic`, `filetype`, `puremagic` in `requirements.txt`, **zero imports** |
| Config flags | `validation_auto_detect_format`, archive settings **unwired** |
| API | `FileDetectionResponse` schema existed; **no** `GET /validate/local/detect` |
| Delimiter sniff | Separate **512 KiB** read in `delimiter_detection.py` |
| Archives | No gzip decompress or zip/tar inspect in validation path |
| Benchmark | `scripts/benchmark_file_detection.py` failed with `ModuleNotFoundError` |

### Performance (legacy)

| Metric | Legacy extension-only |
|--------|----------------------|
| Time | ~0.01 ms per file (in-process suffix check) |
| Memory | Negligible |
| Disk I/O | None |
| Network | N/A for local detect |

### Risks identified

1. **Correctness** — `.csv` containing gzip/JSON/Parquet routed as CSV (test case #46 unmet).
2. **Scalability** — JSON compare path could `read_bytes()` full file (separate from detection).
3. **Memory** — Avro adapter loads entire file; delimiter + future detection duplicate reads.
4. **Ops drift** — Docs promised features that were not in the tree.

## Post-upgrade state

Implemented `pegasus.validation.file_detection` with nine layers, bounded `read_file_sample()` (≤64 KiB), plugin registry, archive materialization helpers, delimiter bridge, and API integration.

| Component | Path |
|-----------|------|
| Pipeline | `pegasus/validation/file_detection/pipeline.py` |
| Layers | `pegasus/validation/file_detection/layers/*.py` |
| Coerce / auto | `pegasus/validation/file_detection/coerce.py` |
| Archives | `pegasus/validation/file_detection/archive_extract.py` |
| Delimiter bridge | `pegasus/validation/file_detection/delimiter_bridge.py` |
| Detect API | `GET /api/v1/validate/local/detect` |
| Local validate | `coerce_local_validate_fields_with_detection()` when `file_format=auto` |

### Performance (pipeline)

See [benchmarks/file-detection-results.md](benchmarks/file-detection-results.md). Pipeline cost is **O(64 KiB)** I/O per file; suitable for 40GB+ inputs and stateless workers.

### Remaining follow-ups

- Merge delimiter sniff (512 KiB) with detection prefix on validate hot path
- Wire `materialize_validation_path()` into `job_worker` before delimited reads
- Recursive nested archive walk (depth-limited)
- Cloud object prefix detection at GCS/S3 read time
- Unit tests for zip/tar listing and parquet footer magic

## Architecture diagram

See [file-type-detection-architecture.md](file-type-detection-architecture.md) for the canonical mermaid pipeline and dataset model table.
