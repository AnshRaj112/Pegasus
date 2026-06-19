# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-19T09:22:58Z
# --- END GENERATED FILE METADATA ---

"""Service-layer errors mapped to HTTP responses by the API layer."""


class ValidationServiceError(Exception):
    """Base class for validation workflow failures."""


class ValidationBadRequestError(ValidationServiceError):
    """Invalid input files or CSV parameters (HTTP 400)."""


class ValidationUnprocessableError(ValidationServiceError):
    """Frames cannot be compared as requested (HTTP 422)."""


def format_validation_job_error(exc: BaseException) -> str:
    """Return a short, user-facing message for failed async validation jobs."""
    if isinstance(exc, ValidationServiceError):
        msg = str(exc).strip()
        return msg or exc.__class__.__name__
    if exc.args:
        first = exc.args[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    text = str(exc).strip()
    return text or type(exc).__name__
