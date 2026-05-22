# Scripts Guide

This page explains every utility script under `scripts/`, what it does, what inputs it expects, and how to run it safely.

## What The Scripts Folder Is For

- Generating reproducible validation fixtures.
- Creating sample fixed-width and JSON datasets for manual testing.
- Producing encryption keys for validation persistence.
- Validating large fixed-width datasets with a custom JSON config.

## How To Run Python Scripts In This Repo

Most scripts can be run from the repository root with the backend environment active.

```bash
cd pegasus-backend
source .venv/bin/activate
python ../scripts/<script_name>.py
```

For scripts that import Pegasus modules directly, set `PYTHONPATH=pegasus-backend/src` or run them from a backend environment where the package is available.

## `generate_db_encryption_key.py`

Purpose:

- Prints a new Fernet key to standard output.
- Use this value for `PEGASUS_DATABASE_ENCRYPTION_KEY` when validation persistence is enabled.

How to run:

```bash
python scripts/generate_db_encryption_key.py
```

What to put in the environment:

- Copy the printed value into `PEGASUS_DATABASE_ENCRYPTION_KEY`.
- Keep it secret and stable for the database you are using.

## `generate_fixed_width_date.py`

Purpose:

- Interactively creates paired fixed-width source and target files.
- Introduces a configurable number of mismatches.
- Shuffles target chunks so row order does not match source order.

How to run:

```bash
python scripts/generate_fixed_width_date.py
```

What it asks for:

- Total number of rows to generate.
- Number of mismatches to inject.
- Output folder name under `test-data/`.

What it produces:

- `test-data/<folder>/source_data.txt`
- `test-data/<folder>/target_data.txt`

What to check after running:

- Confirm the output folder exists.
- Confirm the target file has the requested number of injected mismatches.
- Confirm the date format differs between source and target as intended.

## `generate_json_file.py`

Purpose:

- Creates paired JSON source and target files.
- Reorders nested records and injects a configurable number of mismatches.

How to run:

```bash
python scripts/generate_json_file.py --folder generated-test-json --count 10 --mismatches 3
```

Required inputs:

- `--folder`: output folder under `test-data/`.

Optional inputs:

- `--count`: number of records in the array.
- `--mismatches`: number of explicit mismatches to inject.

What it produces:

- `test-data/<folder>/source.json`
- `test-data/<folder>/target.json`

What to put in it:

- Choose a folder name that matches the scenario you want to document.
- Use a small count for quick manual checks.
- Use a higher mismatch count only when you want to test aggregation or reporting.

## `generate_validation_data.py`

Purpose:

- Generates large CSV fixture pairs with exact mismatch accounting.
- Writes a `manifest.json` file so you can compare expected and actual results.
- Supports `missing`, `extra`, and `value-mismatch` scenarios at scale.

Example runs:

```bash
python scripts/generate_validation_data.py --source-rows 5000 --missing 200 --extra 50 --value-mismatch-uids 300 --out-dir test-data/generated
```

```bash
python scripts/generate_validation_data.py --source-rows 1000000 --columns 8 --out-dir ./test-data/generated-1m-8cols
```

```bash
python scripts/generate_validation_data.py --source-rows 100000000 --missing 1000000 --extra 500000 --value-mismatch-uids 2000000 --out-dir ./test-data/generated-100m
```

Required inputs:

- `--source-rows`: row count for the source file.
- `--out-dir`: destination folder unless `--dry-run` is used.

Important inputs:

- `--missing`: rows that exist only in the source.
- `--extra`: rows that exist only in the target.
- `--value-mismatch-uids`: overlap UIDs that should differ in value.
- `--value-mismatch-columns`: how many compared columns differ per mismatched UID.
- `--columns`: total columns including the UID column.
- `--delimiter`: field separator written into the CSV files.
- `--uid-column`: the join key name written into both files.
- `--target-order`: ordering mode for target overlap rows.
- `--dry-run`: prints the manifest only.

What it produces:

- `source.csv`
- `target.csv`
- `manifest.json`

What to put in it:

- Use `--dry-run` first when you only need the expected mismatch counts.
- Use a real writable directory on your machine.
- Keep `--target-order` in mind when testing sorted versus unsorted comparison paths.
- Use the manifest as the ground truth for test assertions.

## `validate_fixed_width.py`

Purpose:

- Streams two large fixed-width files and compares a configured date slice.
- Writes a mismatch log and prints a summary report.

How to run:

```bash
python scripts/validate_fixed_width.py --config config.json
```

What the config file must contain:

- Top-level `source`, `target`, and `validation` sections.
- `source.file_path` and `target.file_path`.
- `source.date_field` and `target.date_field` with `start`, `end`, and `format`.
- Optional `validation.mismatch_log_path`.
- Optional `validation.report_interval_rows`.

Example config shape:

```json
{
  "source": {
    "file_path": "test-data/generated-10k-fixed_width/source_data.txt",
    "date_field": {
      "start": 58,
      "end": 68,
      "format": "%d/%m/%Y"
    }
  },
  "target": {
    "file_path": "test-data/generated-10k-fixed_width/target_data.txt",
    "date_field": {
      "start": 58,
      "end": 68,
      "format": "%Y/%m/%d"
    }
  },
  "validation": {
    "mismatch_log_path": "mismatches.log",
    "report_interval_rows": 1000000
  }
}
```

What to put in it:

- Point `file_path` at actual source and target files on disk.
- Use byte slices that match the real fixed-width layout.
- Set `format` strings that match the source and target date strings exactly.
- Set `report_interval_rows` lower if you want more frequent progress logs.

## Script Safety Notes

- `generate_fixed_width_date.py` is interactive and writes files immediately after prompts are answered.
- `generate_validation_data.py` can create very large files, so choose output locations with enough disk space.
- `validate_fixed_width.py` reads large files sequentially and can be used against production-sized fixtures if the config is correct.
- `generate_db_encryption_key.py` should be run only when you need a new persistent encryption key.
