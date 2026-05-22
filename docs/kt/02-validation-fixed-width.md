# Fixed-Width Validation

Fixed-width validation is used when records are stored in aligned character slices instead of delimited columns.

## When It Is Used

- The source and target files are plain text records with fixed character positions.
- The user needs a layout preview before validation.
- The data is represented as visually aligned fields rather than comma-separated values.

## User Inputs

- Source path and target path.
- File layout preview or inferred column slices.
- UID or join key for matching rows.
- Date normalization settings when field formats vary.

## Core Behavior

- The layout preview inspects the first non-empty line of each file.
- Slice boundaries are inferred so users can review the expected columns.
- Fixed-width date helpers normalize format strings and parse dates consistently.
- Fuzzy pair matching can be used to pair rows by a join key when exact alignment is not enough.
- Row differences are produced through the same mismatch reporting model used by other validation paths.

## Supporting Logic

- Layout preview and metadata extraction.
- Line diff helpers for fixed-width comparisons.
- Date parsing and normalization helpers.
- Join-key pairing helpers for fuzzy row matching.

## Typical Failure Modes

- The inferred slices do not match the real field boundaries.
- The UID or join key is not stable across files.
- Date fields are encoded with different formats and need normalization.
- A file contains leading or trailing noise lines that shift the layout preview.

## What To Check First

- Inspect the layout preview before running the full comparison.
- Verify the first non-empty row is representative.
- Confirm date formats are captured in the normalization rules.
- Compare a small sample before validating the full dataset.
