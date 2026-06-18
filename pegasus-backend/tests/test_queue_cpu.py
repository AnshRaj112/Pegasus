# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T22:00:00Z
# --- END GENERATED FILE METADATA ---

"""Tests for FCFS queue CPU slot math."""

from __future__ import annotations

from pegasus.core.config import Settings
from pegasus.services.queue_cpu import (
    allocate_cores_per_job,
    max_concurrent_by_cpu,
    schedulable_cpu_cores,
)


def test_schedulable_cpu_reserves_one_core() -> None:
    settings = Settings(validation_cpu_reserve_cores=1)
    assert schedulable_cpu_cores(settings, ncpu=4) == 3


def test_max_concurrent_one_core_per_job() -> None:
    settings = Settings(validation_cpu_reserve_cores=1, validation_min_cpu_per_job=1)
    assert max_concurrent_by_cpu(settings, ncpu=4) == 3


def test_allocate_splits_evenly() -> None:
    settings = Settings(validation_cpu_reserve_cores=1, validation_min_cpu_per_job=1)
    assert allocate_cores_per_job(settings, concurrent_jobs=1, ncpu=4) == 3
    assert allocate_cores_per_job(settings, concurrent_jobs=3, ncpu=4) == 1
