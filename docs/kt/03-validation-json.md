# JSON Validation

JSON validation is used when the file payload is document-like instead of row-based CSV content.

## When It Is Used

- The file format is JSON.
- The validation path uses a document-level UID such as `document`.
- The UI explicitly selects JSON mode instead of CSV mode.

## Core Behavior

- The frontend sends a JSON-specific request shape to the validation endpoint.
- The backend uses the JSON comparison path instead of delimiter-driven CSV parsing.
- The output still follows the same mismatch summary model as the tabular paths.

## Supporting Logic

- JSON comparison helpers.
- General compare-rule and mismatch-reporting infrastructure.
- History persistence and dashboard metrics, which are shared across formats.

## Typical Failure Modes

- The payload is not valid JSON.
- The selected UID field does not exist in the document.
- The expected document structure differs between source and target.
- Nested fields are not normalized the way the comparison expects.

## What To Check First

- Verify both files parse as valid JSON.
- Verify the document key used as the UID is present on both sides.
- Confirm the frontend request sent `file_format=json` and the document UID.
