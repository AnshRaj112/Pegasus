"""UID generation failures."""


class UIDGeneratorError(RuntimeError):
    """Base error for UID generation."""


class UIDColumnNotFoundError(UIDGeneratorError, KeyError):
    """Raised when a requested source column is not in the frame schema."""


class UIDConfigurationError(UIDGeneratorError, ValueError):
    """Raised for invalid generator options (empty keys, duplicate output name, etc.)."""
