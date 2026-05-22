# Tests

This file is the single reference for the current automated test coverage in the backend.

## Test Philosophy

The suite is organized by behavior rather than by framework layer. Most tests are narrow, format-specific, or service-specific so failures point to the exact subsystem that regressed.

## How To Run The Test Suite

Run everything:

```bash
cd pegasus-backend
pytest
```

Run a single file:

```bash
pytest tests/test_fixed_width_dates.py
```

Run a single test function:

```bash
pytest tests/test_api_validate.py -k local
```

Run with verbose output:

```bash
pytest -vv
```

The backend test suite assumes the backend dependencies are installed and, for database-backed tests, that the database configuration is valid.

## Validation And API Tests

- `test_api_validate.py`: main validation API behavior, request payload handling, and response shape.
- `test_api_validate_local.py`: the local validation path, local-path handling, and orchestration behavior.
- `test_validation_history_api.py`: history listing, lookup, daily statistics, deletion, and persistence edge cases.

## Validation Core And Comparison Tests

- `test_compare_rules.py`: compare-rule construction and rule behavior.
- `test_value_compare.py`: value-level comparison semantics.
- `test_uid_based_comparator.py`: UID-based comparison behavior.
- `test_uid_partition.py`: UID partitioning behavior for large comparisons.
- `test_sha256_uid_generator.py`: UID generation based on SHA-256 composite keys.
- `test_mismatch_sample.py`: mismatch sample extraction and grouping rules.

## Format And Reader Tests

- `test_polars_csv_reader.py`: CSV reading behavior through Polars.
- `test_delimiter_tokens.py`: delimiter token handling.
- `test_delimiter_shared_resolve.py`: shared delimiter resolution.
- `test_format_profiles.py`: format profile behavior.
- `test_file_pair.py`: file pairing logic and source/target validation.
- `test_json_compare.py`: JSON comparison behavior.

## Fixed-Width Tests

- `test_fixed_width_layout.py`: layout inference.
- `test_fixed_width_meta.py`: fixed-width metadata handling.
- `test_fixed_width_dates.py`: date parsing and normalization.
- `test_fixed_width_line_diff.py`: line diff behavior for fixed-width records.
- `test_footer_validation.py`: footer validation logic for row-oriented and fixed-width-like inputs.

## Service, Queue, And Resource Tests

- `test_queue_resource_policy.py`: queue-to-resource policy behavior.
- `test_validation_job_queue.py`: validation queue management.
- `test_reconciliation_coordinator.py`: reconciliation coordination.
- `test_resource_tuning.py`: host resource tuning and partition limits.
- `test_database_config.py`: database configuration loading and related settings.

## How To Map A Failure To The Owning Layer

- API test failures usually point to request parsing, dependency injection, response serialization, or permissions.
- Reader and delimiter failures point to file-format handling.
- Comparator and mismatch failures point to the core reconciliation math.
- Queue and resource tests point to execution scaling rather than comparison correctness.
- History tests point to persistence, encryption, migrations, or database reachability.

## Gaps To Know About

- There are no frontend test files in the repository yet.
- The suite is backend-heavy, so manual validation of the UI still matters.

