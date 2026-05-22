# JSON Validation

JSON validation is used when the file payload is document-like instead of row-based CSV content.

## When It Is Used

- The file format is JSON.
- The validation path uses a document-level UID such as `document`.
- The UI explicitly selects JSON mode instead of CSV mode.
- The data is easier to reason about as documents or arrays than as flat rows.

## User Inputs

- Source path and target path.
- JSON mode selected from the validation panel.
- A UID/document key that exists on both sides.
- The same source and target paths that would be used for a file-based run.

## What The Backend Actually Does

1. The frontend sends a JSON-specific request shape to the validation endpoint.
2. The backend uses the JSON comparison path instead of delimiter-driven CSV parsing.
3. The JSON comparator traverses the document structure and compares corresponding values.
4. The output still follows the same mismatch summary model as the tabular paths.
5. The result can be persisted and surfaced in history just like a CSV run.

## Supporting Logic

- JSON comparison helpers.
- General compare-rule and mismatch-reporting infrastructure.
- History persistence and dashboard metrics, which are shared across formats.
- The same validation service orchestration that powers CSV validation.

## How To Validate A JSON Flow Manually

1. Generate or choose a JSON fixture pair.
2. Use the UI or API path that explicitly selects JSON mode.
3. Confirm the request body includes the document UID.
4. Compare the result counts with the known mismatches in the fixture.
5. Check the history page if persistence is enabled.

## Typical Failure Modes

- The payload is not valid JSON.
- The selected UID field does not exist in the document.
- The expected document structure differs between source and target.
- Nested fields are not normalized the way the comparison expects.
- The user accidentally sends the request as CSV mode instead of JSON mode.

## What To Check First

- Verify both files parse as valid JSON.
- Verify the document key used as the UID is present on both sides.
- Confirm the frontend request sent `file_format=json` and the document UID.
- Confirm the backend response includes JSON-mode comparison metadata.
