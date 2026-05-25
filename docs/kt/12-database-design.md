# Database Design

This page explains how Pegasus stores validation history and mismatch data in PostgreSQL.

It covers the main tables, their columns, relationships, indexing strategy, persistence rules, and the operational requirements needed for the schema to work.

## What The Database Is For

The database stores durable records for validation runs and mismatch rows so the product can:

- Show history.
- Show daily stats and trends.
- Load one run’s detail page later.
- Delete or filter past validations.
- Keep enough metadata for debugging and reporting.

## Core Tables

### `validation_runs`

This is the main record for one validation execution.

One row represents one source/target run.

Important fields include:

- `id`: UUID primary key.
- `status`: lifecycle state such as pending, running, completed, or failed.
- `source_filename` / `target_filename`: encrypted file names.
- `source_path` / `target_path`: encrypted file paths or labels.
- `file_pair_key`: hash used to group the same logical file pair.
- `uid_column`: the join key used for comparison.
- `delimiter`: normalized delimiter metadata.
- `column_mappings`: JSON structure describing mapped columns.
- `compared_columns`: JSON structure describing which columns were actually compared.
- `mapping_format_checks`: validation output for header and mapping analysis.
- `footer_validation`: footer-validation result payload.
- `validate_header_formats` / `validate_footers`: booleans describing optional checks.
- Duration fields: upload, validation, and total runtime.
- Count fields: missing, extra, value mismatch, and total mismatch.
- Row counts and compared-column counts.
- `is_match`: whether the run had zero mismatches.
- `error_detail`: encrypted failure detail for failed runs.
- `created_at`, `updated_at`, `started_at`, `completed_at`: timestamps for lifecycle tracking.

### `mismatch_reports`

This table stores the long-form mismatch rows for a validation run.

Each row represents one specific mismatch item, not one whole validation job.

Important fields include:

- `id`: UUID primary key.
- `validation_run_id`: foreign key back to `validation_runs`.
- `uid`: the row identifier for the mismatch.
- `mismatch_type`: missing-in-target, extra-in-target, or value-mismatch.
- `column_name`: the compared column name for value mismatches.
- `source_value`: the value from the source file.
- `target_value`: the value from the target file.
- `row_detail`: a serialized row snapshot for troubleshooting.
- `created_at`: row insertion time.

## Relationships

The relationship is one-to-many:

- One validation run can have many mismatch report rows.
- Every mismatch row belongs to exactly one validation run.

When a run is deleted, its mismatch rows are deleted with it.

## Status Lifecycle

Pegasus uses a simple run lifecycle:

- `pending`: the run has been created but not yet started.
- `running`: the backend is actively processing it.
- `completed`: the run finished successfully.
- `failed`: the backend encountered an error.

This lifecycle matters because the history UI and daily stats query terminal states differently.

## Persistence Flow

1. A run starts and a `validation_runs` row is created in `running` state.
2. The backend executes the validation.
3. On success, the run summary fields are updated.
4. The mismatch rows are inserted into `mismatch_reports`.
5. On failure, the run is marked failed and the error detail is stored.

This is handled by the repository layer, not by the UI.

## What Gets Stored On Success

When the run completes successfully, the repository stores:

- Final status.
- Mismatch counts.
- Source and target row counts.
- Compared column metadata.
- Mapping and footer analysis results when present.
- Duration fields when present.
- The full mismatch row set.

The `is_match` flag is set based on whether the total mismatch count is zero.

## What Gets Stored On Failure

When validation fails, the repository stores:

- Final status `failed`.
- An encrypted error message.
- Completion timestamps.

The mismatch table may remain empty if the run failed before producing mismatch rows.

## Indexing Strategy

The main explicit index in the model is:

- `ix_validation_runs_file_pair_key_created_at` on `file_pair_key` and `created_at`.

This supports history views that need to find the latest runs for the same file pair.

There is also a foreign-key index on `mismatch_reports.validation_run_id` so the detail page can load mismatch rows efficiently.

## Why Encryption Is Used

Pegasus encrypts sensitive text fields before writing them to the database.

That includes:

- File names and paths.
- UID and delimiter metadata.
- Comparison metadata fields.
- Error details.

This design reduces the amount of plain text operational data stored in PostgreSQL.

## Operational Requirements

### Database URL

The backend needs a valid `PEGASUS_DATABASE_URL` or compatible `DB_*` configuration.

### Encryption Key

If validation persistence is enabled, `PEGASUS_DATABASE_ENCRYPTION_KEY` must be set.

Without it, startup should fail fast rather than silently store unencrypted data.

### Schema And Migrations

The schema must exist before the migration runs, and Alembic must be applied before persistence-backed endpoints work.

If the schema is missing, history and persistence operations will fail.

## How History Queries Use The Schema

- Daily stats group by `completed_at` and use terminal statuses.
- List queries sort by `created_at` descending.
- Run detail queries load one `validation_runs` row by primary key.
- Mismatch detail queries load rows by `validation_run_id`.

That means the same schema supports the dashboard, history view, and run detail page.

## What Happens When Persistence Is Disabled

The validation itself still runs.

What you lose is:

- The history list.
- Daily stats.
- Saved run detail pages.
- Mismatch rows in the database.

The backend explicitly treats this as a feature flag rather than a partial failure.

## Common Database Failure Modes

- Missing schema.
- Missing or wrong database URL.
- Missing encryption key when persistence is enabled.
- Migration not applied.
- Database connection not reachable from the API process.
- Permission problems on the schema or tables.

## Recommended Checks When Debugging

1. Confirm the backend can connect to PostgreSQL.
2. Confirm the schema exists.
3. Confirm migrations are up to date.
4. Confirm the encryption key is present.
5. Confirm persistence is enabled.
6. Confirm history endpoints return rows for a recent successful run.

## Relationship To The Code

- The ORM models live in [pegasus-backend/src/pegasus/models](../../pegasus-backend/src/pegasus/models).
- Persistence helpers live in [pegasus-backend/src/pegasus/repositories/validation_repository.py](../../pegasus-backend/src/pegasus/repositories/validation_repository.py).
- History endpoints live in [pegasus-backend/src/pegasus/api/v1/validation_history.py](../../pegasus-backend/src/pegasus/api/v1/validation_history.py).

Understanding those three areas is enough to debug almost every persistence issue.

## What To Read Next

- [Backend logic](04-backend-logic.md) for how the database is reached from the validation pipeline.
- [Tests](06-tests.md) for persistence and history coverage.
