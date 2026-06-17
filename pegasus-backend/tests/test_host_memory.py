# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T16:00:00Z
# --- END GENERATED FILE METADATA ---

"""Tests for host memory probing."""

from __future__ import annotations

from pegasus.services.host_memory import available_worker_memory_bytes


def test_available_worker_memory_respects_reserve() -> None:
    avail = available_worker_memory_bytes(api_reserve_bytes=2 * 1024**3)
    assert avail >= 512 * 1024 * 1024
