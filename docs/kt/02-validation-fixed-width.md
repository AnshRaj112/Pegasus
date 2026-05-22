# Fixed-Width Validation

Fixed-width validation is used when records are stored in aligned character slices instead of delimited columns.

## When It Is Used

- The source and target files are plain text records with fixed character positions.
- The user needs a layout preview before validation.
- The data is represented as visually aligned fields rather than comma-separated values.
- The row boundaries matter less than the field boundaries.

## User Inputs

- Source path and target path.
- File layout preview or inferred column slices.
- UID or join key for matching rows.
- Date normalization settings when field formats vary.
- Optional fixed-width fixture or validation config file for standalone scripts.

## What The Backend Actually Does

1. It reads the first non-empty line from each file to infer candidate slices.
2. It previews the layout so the user can verify the inferred boundaries.
3. It normalizes date format strings when a date field is part of the comparison.
4. It runs either exact join-key pairing or a fuzzy join-key helper when the data is not perfectly aligned.
5. It emits line-level mismatches, parse failures, or missing-row style records.
6. It streams the result in a way that can handle very large files without loading everything into memory.

## How The Fixed-Width Script Fits In

- `scripts/generate_fixed_width_date.py` creates a source and target pair with the same field layout.
- It injects mismatches into the target file.
- It also reorders the target chunks so validation cannot rely on row order.
- `scripts/validate_fixed_width.py` reads a config JSON and validates the date slice across both files.

## Supporting Logic

- Layout preview and metadata extraction.
- Line diff helpers for fixed-width comparisons.
- Date parsing and normalization helpers.
- Join-key pairing helpers for fuzzy row matching.
- Streaming validation logic for large files.

## How To Validate A Fixed-Width Flow Manually

1. Generate a fixture pair with `generate_fixed_width_date.py`.
2. Open the generated files and verify the field widths line up visually.
3. Run the fixed-width validation script with a matching config JSON.
4. Confirm the mismatch log matches the injected changes.
5. If dates fail, check the start/end offsets and the format strings first.

## Typical Failure Modes

- The inferred slices do not match the real field boundaries.
- The UID or join key is not stable across files.
- Date fields are encoded with different formats and need normalization.
- A file contains leading or trailing noise lines that shift the layout preview.
- The config JSON points to the wrong slice offsets or wrong file paths.

## What To Check First

- Inspect the layout preview before running the full comparison.
- Verify the first non-empty row is representative.
- Confirm date formats are captured in the normalization rules.
- Compare a small sample before validating the full dataset.
- Verify the mismatch log path is writable.
