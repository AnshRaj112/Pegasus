# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Tests for calibrated resource models."""

from __future__ import annotations

from pegasus.services.resource_models import (
    apply_utilization_slack,
    estimate_streaming_job_ram_bytes,
    estimate_streaming_spill_disk_bytes,
)


def test_streaming_disk_matches_footprint_for_40gb() -> None:
    combined = 40 * 1024**3
    est = estimate_streaming_spill_disk_bytes(combined, min_disk_per_job_bytes=50 * 1024**2)
    # Observed ~4.97 GiB; tiered 0.15× → ~6 GiB (conservative).
    assert 4 * 1024**3 <= est <= 7 * 1024**3


def test_streaming_ram_calibrated_for_large_job() -> None:
    combined = 40 * 1024**3
    est = estimate_streaming_job_ram_bytes(
        combined,
        min_ram_per_job_bytes=100 * 1024**2,
        compare_column_count=12,
    )
    # Observed peak RSS ~1.48 GiB.
    assert est >= 1400 * 1024**2


def test_utilization_slack() -> None:
    assert apply_utilization_slack(10, 0.70) == 7
    assert apply_utilization_slack(1, 0.70) == 1
