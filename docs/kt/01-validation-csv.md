# CSV / Delimiter Validation

This is the default validation path for tabular files that use a delimiter such as comma, pipe, tab, or semicolon.

## When It Is Used

- The file format is CSV or another delimited table.
- The user provides a UID column that exists in both source and target.
- The comparison columns are derived from the shared schema or from the mapping wizard.

## User Inputs

- Source path and target path.
- UID column name.
- Delimiter mode, including auto-detection.
- Optional column mappings.
- Optional header-format validation.
- Optional footer validation.

## Core Behavior

- The backend resolves the delimiter before reading rows.
- Column names are read from both files so the UI can suggest matches.
- Compare rules are built from the selected mappings.
- The validation service loads the two datasets and compares them by UID.
- The result includes missing rows, extra rows, mismatched values, and summary counts.

## Supporting Logic

- Delimiter detection and shared delimiter resolution.
- Polars-backed CSV reading.
- Column mapping analysis for the wizard.
- Footer and header format checks when enabled.
- UID-based comparison and mismatch reporting.

## Typical Failure Modes

- The delimiter is wrong and the reader sees one giant column.
- The UID column is missing from one side.
- The source and target headers do not align.
- A mapping references a column that does not exist.
- The footer check fails because the file has extra trailer rows.

## What To Check First

- Confirm the files open as the expected delimiter in a plain text editor.
- Confirm the UID value is present in both files and has a stable type.
- Confirm auto-detection did not choose the wrong delimiter.
- Confirm compare columns exclude the UID column.
