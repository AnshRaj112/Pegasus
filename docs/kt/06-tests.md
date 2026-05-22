# Tests

This file is the single reference for the current automated test coverage in the backend.

## Test Philosophy

The suite is organized by behavior rather than by framework layer. Most tests are narrow, format-specific, or service-specific so failures point to the exact subsystem that regressed.

## Validation And API Tests

- `test_api_validate.py`: validates the main validation API behavior.
- `test_api_validate_local.py`: checks the local validation path and request handling.
- `test_validation_history_api.py`: covers history listing, lookup, and history statistics.

## Validation Core And Comparison Tests

- `test_compare_rules.py`: compare-rule construction and rule behavior.
- `test_value_compare.py`: value-level comparison semantics.
- `test_uid_based_comparator.py`: UID-based comparison behavior.
- `test_uid_partition.py`: UID partitioning behavior for large comparisons.
- `test_sha256_uid_generator.py`: UID generation based on SHA-256 composite keys.

## Format And Reader Tests

- `test_polars_csv_reader.py`: CSV reading behavior through Polars.
- `test_delimiter_tokens.py`: delimiter token handling.
- `test_delimiter_shared_resolve.py`: shared delimiter resolution.
- `test_format_profiles.py`: format profile behavior.
- `test_file_pair.py`: file pairing logic.
- `test_json_compare.py`: JSON comparison behavior.

## Fixed-Width Tests

- `test_fixed_width_layout.py`: layout inference.
- `test_fixed_width_meta.py`: fixed-width metadata handling.
- `test_fixed_width_dates.py`: date parsing and normalization.
- `test_fixed_width_line_diff.py`: line diff behavior for fixed-width records.
- `test_mismatch_sample.py`: mismatch sample extraction, including fixed-width scenarios.

## Service, Queue, And Resource Tests

- `test_queue_resource_policy.py`: queue-to-resource policy behavior.
- `test_validation_job_queue.py`: validation queue management.
- `test_reconciliation_coordinator.py`: reconciliation coordination.
- `test_resource_tuning.py`: host resource tuning and partition limits.
- `test_database_config.py`: database configuration loading.

## Additional Infrastructure Tests

- `test_footer_validation.py`: footer validation logic.
- `test_database_config.py`: environment and database settings behavior.

## How To Read Failures

When a test fails, use the file name to locate the owning subsystem. Validation API failures usually point to request parsing or orchestration. Reader and delimiter failures point to file-format handling. Queue and resource tests point to execution scaling rather than comparison correctness.

## Gaps To Know About

- There are no frontend test files in the repository yet.
- The suite is backend-heavy, so manual validation of the UI still matters.
