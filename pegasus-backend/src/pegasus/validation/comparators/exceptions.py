"""Comparison engine errors."""


class ComparisonError(RuntimeError):
    """Base class for Pegasus validation comparison failures."""


class UIDComparisonError(ComparisonError, ValueError):
    """Raised when inputs are incompatible with UID-based comparison."""
