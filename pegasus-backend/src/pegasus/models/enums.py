# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-19T09:48:25Z
# --- END GENERATED FILE METADATA ---

"""Database-facing enumerations."""

from __future__ import annotations

from enum import StrEnum


class ValidationRunStatus(StrEnum):
    """Lifecycle state for a persisted validation run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
