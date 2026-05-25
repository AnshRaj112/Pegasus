# Backend Logic And Orchestration

This page is the backend KT reference for how Pegasus validation works end to end.

It explains which API route starts a run, how file inputs are resolved, how validation chooses an execution strategy, how the comparison engines work, and how the result becomes history data and dashboard metrics.

## What The Backend Owns

- Input validation for file paths, local/cloud sources, and queue settings.
- Delimiter resolution and fixed-width / JSON branching.
- Column and UID matching.
- In-memory, external-memory, and partitioned reconciliation.
- Mismatch reporting and optional streaming artifacts.
- Persistence, history, and daily dashboard statistics.

## Request Entry Points

- `POST /api/v1/validate/local` starts a local validation run from the UI.
- `GET /api/v1/validate/local/columns` previews source and target headers for mapping.
- `POST /api/v1/validate/history/draft` saves mapping and validation draft data.
- `GET /api/v1/validate/history` lists persisted runs.
- `GET /api/v1/validate/history/daily-stats` powers the dashboard chart.
- `GET /api/v1/validate/queue` and `PATCH /api/v1/validate/queue` expose runtime queue controls.
- `GET /api/v1/validate/history/{run_id}` returns a single persisted run.
- `GET /api/v1/validate/history/{run_id}/mismatches` returns mismatch records for a saved run.

## Request And Input Shapes

The backend accepts several kinds of validation input:

- Local paths supplied by the browser or UI.
- Cloud inputs, currently including Google Cloud Storage references.
- CSV-style files with a selectable delimiter.
- Multi-character delimiter files, which are handled through a pandas fallback when Polars cannot parse them directly.
- Fixed-width validation inputs.
- JSON validation inputs.

For local path validation, Pegasus can optionally allow server-side filesystem paths when `PEGASUS_VALIDATION_ALLOW_LOCAL_PATHS=true`.

## Input Resolution Flow

1. The API checks whether local-path access is enabled.
2. Local paths are resolved to real server paths and verified to be regular files.
3. Cloud objects are downloaded to a temporary path when the request uses cloud references.
4. The backend labels each resolved input with a display name so logs and responses can show where the data came from.
5. Temporary downloads are cleaned up after the run.

## Main Validation Service

`ValidationService` is the central orchestration point for CSV-style validation and format analysis.

It is responsible for:

- Resolving delimiters, including `auto`, `infer`, `detect`, tab, and explicit single or multi-character separators.
- Reading headers for column previews and auto-mapping.
- Building compare rules from explicit column mappings.
- Selecting the reconciliation path based on file size, delimiter style, and queue policy.
- Running the comparison work in a background thread so the event loop stays responsive.
- Returning row counts, compared columns, mismatch artifacts, and timing metadata.

## Validation Lifecycle

1. The API validates the request payload and file paths.
2. The service resolves the delimiter or file layout.
3. Header metadata is read so the backend can identify compare columns.
4. Optional header and footer checks run when requested.
5. File validation confirms both files are readable and parseable.
6. Host-aware tuning adjusts partition buckets using CPU and RAM hints.
7. The engine selects one of three broad execution styles:
	- In-memory UID comparison.
	- External-memory reconciliation for larger CSVs.
	- Multichar delimiter streaming reconciliation.
8. The comparator generates missing, extra, and value-mismatch records.
9. Optional persistence stores the result in history.

## How Validation Chooses Its Execution Path

The service makes the path decision using these signals:

- Whether column mappings are present.
- Whether the delimiter is a single character or multi-character.
- Whether reconciliation is forced externally by configuration.
- Whether the estimated file size crosses the external-memory threshold.
- Whether the runtime queue policy changes the effective worker budget.

### In-Memory CSV Path

The in-memory path is used when the files can safely be loaded into Polars DataFrames.

It does the following:

- Reads both files into DataFrames.
- Validates that the UID column exists on both sides.
- Renames target columns to align explicit mappings when needed.
- Computes the shared compare columns.
- Builds compare rules from the provided mappings.
- Runs the UID-based comparator directly.

This is the simplest path and is easiest to reason about during debugging.

### External-Memory CSV Path

The external-memory path is used for large CSV runs where keeping everything in RAM is not desirable.

It does the following:

- Probes the schema for source and target.
- Verifies the UID column exists in both files.
- Computes compare columns from the shared schema.
- Runs `ReconciliationCoordinator` with a runtime config that respects CPU, RAM, disk, and queue tuning.
- Streams or partitions the comparison instead of loading the full dataset at once.

This is the path to expect for large single-character delimited files when the data size or configuration suggests spill-based reconciliation.

### Multi-Character Delimiter Path

Multi-character delimiters require a different treatment because the Polars CSV parser does not handle them directly.

The backend:

- Reads the headers using a dedicated multichar helper.
- Validates the UID column in both headers.
- Computes the shared compare columns.
- Uses chunked hash-partition reconciliation for the actual run.

This path is important when your data uses separators such as `||`.

## Validation Of Fixed-Width And JSON Inputs

The backend also contains specialized logic for fixed-width and JSON runs.

### Fixed-Width

- The backend expects a structured fixed-width config.
- It validates the existence of source and target files.
- It checks the UID column.
- It validates the slice definitions and date formats.
- It can compare multiple fields or a single date slice depending on the config.

### JSON

- JSON validation uses document-style comparison rather than delimiter parsing.
- The UI sends a JSON-specific payload with a document UID.
- The output still uses the same mismatch-reporting model as CSV validation.

## Comparison Stack

- Readers load source and target data.
- Parsers and normalizers reshape the frames into a comparable form.
- UID generators derive stable keys when the source data does not already provide one.
- Comparators perform row-level or UID-based comparisons.
- Reporters convert the final mismatch set into the artifact format returned to the caller.

## The UID Comparator In Plain English

The comparator rejects duplicate UIDs, because the logic assumes each UID identifies at most one source row and one target row.

For each run it computes:

- Rows that exist in source but not target.
- Rows that exist in target but not source.
- Rows that exist in both but differ on one or more compared columns.

The mismatch output is a long-form table, not a single summary row. That makes it easier to sample and display in the UI.

## Reconciliation And Scale Controls

- Queue resource policy caps or tunes concurrency based on host capacity.
- Resource tuning clamps partition buckets to available CPU and RAM hints.
- Streaming mismatch collection can mirror results to disk when configured.
- External-memory thresholds decide when the engine stops trying to keep everything in RAM.
- Partitioned workers can run in parallel for large bucketed comparisons.

## Persistence And History

- Validation runs can be persisted to the database when persistence is enabled.
- History APIs support daily stats, run lookup, mismatch sampling, and deletion.
- The dashboard reads the same history endpoints to build charts and summaries.
- Persistence requires a database migration and an encryption key.

If persistence is disabled, the run still works, but it will not appear in the history UI.

## Queue And Runtime Controls

The queue settings affect how many validations can run in parallel and how much worker parallelism each job can use.

- `PEGASUS_VALIDATION_MAX_CONCURRENCY` sets the starting queue size.
- `PEGASUS_VALIDATION_AUTO_TUNE_ENABLED` lets the backend reduce concurrency when RAM or disk pressure is high.
- Queue policy is applied again when the validation service prepares the reconciliation runtime.

This is why a run can behave differently on the same machine if queue settings change.

## Common Control Points

- Delimiter resolution happens before column analysis.
- Header and footer checks are optional gates that can fail a run early.
- Queue settings control how much parallel work the backend accepts.
- Reconciliation strategy controls how aggressively the engine falls back to external-memory behavior.
- CORS must be enabled when the frontend origin differs from the API origin.

## Important Environment Behavior

- `PEGASUS_DATABASE_URL` overrides `DB_*` style settings.
- `PEGASUS_DATABASE_ENCRYPTION_KEY` is mandatory when validation persistence is enabled.
- `PEGASUS_CORS_ORIGINS` should contain the Vite dev origin when frontend and backend run separately.
- `PEGASUS_VALIDATION_MAX_UPLOAD_BYTES` sets the per-file upload cap.
- `PEGASUS_ENABLE_VALIDATION_PERSISTENCE` must be true for history and dashboard queries.

## Error Handling And What It Means

- Missing UID columns usually mean the wrong delimiter or wrong header was selected.
- Parse errors usually mean the file is malformed or the delimiter is wrong.
- Duplicate UID errors mean the input is not unique enough for UID-based comparison.
- Validation bad request errors usually mean the input can be corrected and retried.
- Unprocessable errors usually mean the data shape is not compatible with the selected strategy.

## Mental Model For Debugging

If something fails, check the pipeline in this order: request payload, file resolution, delimiter or layout inference, compare rule construction, UID pairing, reconciliation, and finally persistence.

## What New Engineers Should Read Next

- The CSV validation page for the most common run path.
- The fixed-width page for layout and slice-based workflows.
- The scripts guide for fixture generation.
- The tests page for behavior coverage.
