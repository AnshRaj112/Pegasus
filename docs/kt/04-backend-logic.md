# Backend Logic And Orchestration

This page explains how the backend is wired, where the decision points live, and which services control execution.

## Request Entry Points

- API routes under `pegasus.api.v1` accept validation, history, and health requests.
- The local validation endpoint is the main entry point for a run initiated from the UI.
- The history endpoints support listing, deleting, and inspecting completed runs.

## Main Validation Service

- `ValidationService` orchestrates file loading and comparison.
- It resolves delimiters, previews layouts, and analyzes mappings before the comparison starts.
- It can run validation work in a thread so the event loop stays responsive.
- It returns a structured result with row counts, mismatch data, optional artifacts, and timing metadata.

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

## Persistence And History

- Validation runs can be persisted to the database when persistence is enabled.
- History APIs support daily stats, run lookup, mismatch sampling, and deletion.
- The dashboard reads the same history endpoints to build charts and summaries.

## Common Control Points

- Delimiter resolution happens before column analysis.
- Header and footer checks are optional gates that can fail a run early.
- Queue settings control how much parallel work the backend accepts.
- Reconciliation strategy controls how aggressively the engine falls back to external-memory behavior.

## Mental Model For Debugging

If something fails, check the pipeline in this order: request payload, file resolution, delimiter or layout inference, compare rule construction, UID pairing, reconciliation, and finally persistence.
