# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:57:27Z
# --- END GENERATED FILE METADATA ---

"""Partition reconcile parallelism thresholds."""

from __future__ import annotations

from pegasus.validation.pipeline.partition_reconcile import (
    resolved_reconcile_workers,
    should_parallel_reconcile,
)


def test_resolved_reconcile_workers_auto() -> None:
    workers = resolved_reconcile_workers(0)
    assert workers >= 2


def test_should_parallel_reconcile_large_input_lower_bar() -> None:
    gb = 600 * 1024 * 1024
    assert should_parallel_reconcile(num_partitions=16, workers=4, input_bytes=gb)
    assert not should_parallel_reconcile(num_partitions=4, workers=4, input_bytes=gb)


def test_should_parallel_reconcile_small_input_higher_bar() -> None:
    assert should_parallel_reconcile(num_partitions=32, workers=4, input_bytes=1024)
    assert not should_parallel_reconcile(num_partitions=16, workers=4, input_bytes=1024)
