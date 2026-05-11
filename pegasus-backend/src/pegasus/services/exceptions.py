"""Service-layer errors mapped to HTTP responses by the API layer."""


class ValidationServiceError(Exception):
    """Base class for validation workflow failures."""


class ValidationBadRequestError(ValidationServiceError):
    """Invalid input files or CSV parameters (HTTP 400)."""


class ValidationUnprocessableError(ValidationServiceError):
    """Frames cannot be compared as requested (HTTP 422)."""
