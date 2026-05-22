# Backend Logic And Orchestration

This page explains how the backend is wired, where the decision points live, and which services control execution.

## Request Entry Points

- API routes under `pegasus.api.v1` accept validation, history, and health requests.
- `POST /api/v1/validate/local` is the main entry point for a local validation run initiated from the UI.
- `GET /api/v1/validate/history` lists persisted runs.
- `GET /api/v1/validate/history/daily-stats` powers the dashboard chart.
- `GET /api/v1/validate/queue` and `PATCH /api/v1/validate/queue` expose runtime queue controls.

## Main Validation Service

- `ValidationService` orchestrates file loading and comparison.
- It resolves delimiters, previews layouts, and analyzes mappings before the comparison starts.
- It can run validation work in a thread so the event loop stays responsive.
- It returns a structured result with row counts, mismatch data, optional artifacts, and timing metadata.
- It also prepares runtime reconciliation configuration and applies host-aware tuning before large jobs start.

## Execution Pipeline In Order

1. The API validates the request payload and file paths.
2. The service resolves delimiter, layout, mapping, and optional header/footer behavior.
3. Reader code loads the source and target into a comparable intermediate form.
4. Compare rules are built from the selected columns and mappings.
5. UID logic determines how rows are matched.
6. Reconciliation logic decides whether the comparison stays in memory, streams, partitions, or spills to disk.
7. The comparator generates missing, extra, and value-mismatch records.
8. Reporters and repositories optionally persist the run and expose it through the history API.

## Comparison Stack

- Readers load source and target data.
- Parsers and normalizers reshape the frames into a comparable form.
- UID generators derive stable keys when the source data does not already provide one.
- Comparators perform row-level or UID-based comparisons.
- Reporters convert the final mismatch set into the artifact format returned to the caller.

## Reconciliation And Scale Controls

- Large jobs can use reconciliation workers and partitioned processing.
- Queue resource policy caps or tunes concurrency based on host capacity.
- Resource tuning clamps partition buckets to available CPU and RAM hints.
- Streaming mismatch collection can mirror results to disk when configured.
- External-memory thresholds decide when the engine stops trying to keep everything in RAM.

## Persistence And History

- Validation runs can be persisted to the database when persistence is enabled.
- History APIs support daily stats, run lookup, mismatch sampling, and deletion.
- The dashboard reads the same history endpoints to build charts and summaries.
- Persistence requires both a database schema migration and an encryption key.

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

## Mental Model For Debugging

If something fails, check the pipeline in this order: request payload, file resolution, delimiter or layout inference, compare rule construction, UID pairing, reconciliation, and finally persistence.
