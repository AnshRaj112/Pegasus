# CSV / Delimiter Validation

This is the default validation path for tabular files that use a delimiter such as comma, pipe, tab, or semicolon.

## When It Is Used

- The file format is CSV or another delimited table.
- The user provides a UID column that exists in both source and target.
- The comparison columns are derived from the shared schema or from the mapping wizard.
- The row order may be different between source and target, because matching happens by UID instead of by physical row number.

## User Inputs

- Source path and target path.
- UID column name.
- Delimiter mode, including auto-detection.
- Optional column mappings.
- Optional header-format validation.
- Optional footer validation.
- Optional local-path browsing when the backend allows it.

## What The Backend Actually Does

1. It resolves the delimiter, either from user input or through shared auto-detection.
2. It reads headers from both files so the UI can compare source and target columns.
3. It subtracts the UID column from the compare set.
4. It builds compare rules from the mapped or automatically matched columns.
5. It loads the full pair through the validation service or a reconciliation worker, depending on size and runtime policy.
6. It produces missing-row, extra-row, and value-mismatch records.
7. It returns counts, mismatch samples, and optional artifacts back to the API caller.

## Validation Result Shape

The result usually contains:

- Source and target row counts.
- Compared column count.
- The exact set of compared columns.
- Missing-in-target mismatch counts.
- Extra-in-target mismatch counts.
- Value mismatch counts.
- Sample mismatch rows for the UI.
- Timing metadata for upload, comparison, and total runtime.

## Supporting Logic

- Delimiter detection and shared delimiter resolution.
- Polars-backed CSV reading.
- Column mapping analysis for the wizard.
- Footer and header format checks when enabled.
- UID-based comparison and mismatch reporting.
- History persistence if the run is configured to be saved.

## How To Validate A CSV Flow Manually

1. Start the backend and frontend.
2. Use a small fixture pair with a known UID column.
3. Run a validation with `delimiter=auto` once and with the explicit delimiter once.
4. Compare the counts against the generated fixture manifest or known mismatch set.
5. Open the history page and confirm the run appears when persistence is enabled.

## Typical Failure Modes

- The delimiter is wrong and the reader sees one giant column.
- The UID column is missing from one side.
- The source and target headers do not align.
- A mapping references a column that does not exist.
- The footer check fails because the file has extra trailer rows.
- The run is accepted but the queue is too busy, so the UI appears to stall.

## What To Check First

- Confirm the files open as the expected delimiter in a plain text editor.
- Confirm the UID value is present in both files and has a stable type.
- Confirm auto-detection did not choose the wrong delimiter.
- Confirm compare columns exclude the UID column.
- Confirm the backend log shows the same delimiter the UI selected.
