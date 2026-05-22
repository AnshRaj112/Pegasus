# Overview

Pegasus is a file validation and reconciliation platform. The user uploads two files, chooses a validation mode, and the system compares the source and target data to produce a mismatch report, history entry, and dashboard metrics.

## What The Platform Does

- Compares two datasets by a UID or document key.
- Detects missing rows, extra rows, and value mismatches.
- Supports CSV-style delimiter parsing, fixed-width layout analysis, and JSON validation paths.
- Stores validation history so users can revisit prior runs.
- Surfaces the job queue and validation health through the UI.

## Main Runtime Flow

1. The frontend gathers file paths, file format, UID selection, delimiter, and optional mapping settings.
2. The API receives the request and validates inputs.
3. The backend loads files, resolves delimiters or layouts, and builds comparison rules.
4. The comparison engine runs either directly or through reconciliation workers for large inputs.
5. Mismatch artifacts and summary metadata are returned to the caller and, when enabled, persisted to history.

## Primary Code Areas

- API layer: request validation, job control, history endpoints.
- Services: orchestration, queue management, resource tuning, persistence.
- Validation package: readers, comparators, parsers, reconciliation, format helpers.
- Frontend: upload flow, mapping wizard, results, history dashboard, resource controls.

## Validation Modes At A Glance

- CSV / delimiter validation: best fit for standard delimited files and auto-detected delimiters.
- Fixed-width validation: best fit for files with character-based column layouts.
- JSON validation: best fit for document-style records with a document UID.

## What New Engineers Should Remember

- The system is built around the validation service, not around the UI.
- Queue tuning and reconciliation strategy matter for large datasets.
- Most user-visible failures are caused by bad paths, delimiter mismatch, malformed data, or schema/history configuration issues.
