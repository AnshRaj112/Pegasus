"""Errors raised by the external-memory reconciliation engine."""


class ReconciliationError(RuntimeError):
    """Base class for reconciliation failures (I/O, configuration, or Polars errors)."""


class ReconciliationStrategyError(ReconciliationError):
    """Raised when the chosen strategy cannot run with the supplied inputs."""

