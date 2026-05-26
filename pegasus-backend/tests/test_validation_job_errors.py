"""User-facing error formatting for async validation jobs."""

from __future__ import annotations

from pegasus.services.exceptions import (
    ValidationBadRequestError,
    format_validation_job_error,
)


def test_format_validation_job_error_service_exception() -> None:
    exc = ValidationBadRequestError("Both source and target files are empty (no data rows).")
    assert format_validation_job_error(exc) == "Both source and target files are empty (no data rows)."


def test_format_validation_job_error_avoids_repr() -> None:
    exc = ValidationBadRequestError("Both source and target files are empty (no data rows).")
    assert "ValidationBadRequestError" not in format_validation_job_error(exc)
