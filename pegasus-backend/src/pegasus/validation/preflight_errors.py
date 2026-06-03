"""Shared preflight exception types (avoids import cycles)."""


class CsvPreflightError(ValueError):
    """CSV structure is invalid for validation."""
