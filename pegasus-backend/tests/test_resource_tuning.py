# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T09:57:42Z
# --- END GENERATED FILE METADATA ---

"""Tests for :mod:`pegasus.core.resource_tuning`."""

from pegasus.core import resource_tuning as rt


def test_max_partitions_scales_with_ram_and_cpus() -> None:
    assert rt.max_reconciliation_partition_buckets(ncpu=4, ram_bytes=15 * 1024**3) <= 64
    assert rt.max_reconciliation_partition_buckets(ncpu=4, ram_bytes=15 * 1024**3) >= 16
    low = rt.max_reconciliation_partition_buckets(ncpu=2, ram_bytes=4 * 1024**3)
    high = rt.max_reconciliation_partition_buckets(ncpu=16, ram_bytes=64 * 1024**3)
    assert low <= high


def test_align_partitions_to_threads() -> None:
    assert rt.align_partition_buckets_to_threads(512, 4) == 64
    assert rt.align_partition_buckets_to_threads(24, 4) == 24


def test_cap_partition_buckets() -> None:
    mx = rt.max_reconciliation_partition_buckets(ncpu=4, ram_bytes=16 * 1024**3)
    assert rt.cap_partition_buckets(4096, ncpu=4, ram_bytes=16 * 1024**3) == mx
    large = rt.cap_partition_buckets(
        512,
        ncpu=4,
        ram_bytes=16 * 1024**3,
        combined_file_bytes=4 * 1024**3,
    )
    assert large >= 256
    low_request = rt.cap_partition_buckets(
        32,
        ncpu=4,
        ram_bytes=16 * 1024**3,
        combined_file_bytes=4 * 1024**3,
    )
    assert low_request >= 256


def test_effective_local_threads_never_exceeds_ncpu() -> None:
    assert rt.effective_local_thread_cap(256, ncpu=4) == 4
    assert rt.effective_local_thread_cap(0, ncpu=8) == 8
