"""Lightweight metrics hooks for reconciliation (no-op default)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReconciliationMetrics(Protocol):
    """Optional callbacks for observability (logging, Prometheus, tracing spans, etc.)."""

    def on_phase_start(self, phase: str, **kwargs: Any) -> None:
        """Called when a named phase of the coordinator begins."""

    def on_phase_end(self, phase: str, **kwargs: Any) -> None:
        """Called when a phase completes successfully."""

    def on_rows_processed(self, side: str, rows: int, **kwargs: Any) -> None:
        """Called after a batch of rows is read or written for *side* (``\"source\"`` / ``\"target\"``)."""

    def on_partition_done(self, partition_id: int, **kwargs: Any) -> None:
        """Called after a hash partition finishes comparing."""

    def on_retry(self, attempt: int, error: BaseException, **kwargs: Any) -> None:
        """Called when a retriable operation is retried."""


class NoOpReconciliationMetrics:
    """Default metrics implementation that performs no work."""

    def on_phase_start(self, phase: str, **kwargs: Any) -> None:  # noqa: ARG002
        return None

    def on_phase_end(self, phase: str, **kwargs: Any) -> None:  # noqa: ARG002
        return None

    def on_rows_processed(self, side: str, rows: int, **kwargs: Any) -> None:  # noqa: ARG002
        return None

    def on_partition_done(self, partition_id: int, **kwargs: Any) -> None:  # noqa: ARG002
        return None

    def on_retry(self, attempt: int, error: BaseException, **kwargs: Any) -> None:  # noqa: ARG002
        return None
