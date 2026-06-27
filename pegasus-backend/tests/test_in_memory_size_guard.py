# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-27T14:34:06Z
# --- END GENERATED FILE METADATA ---

"""In-memory fast path must not run for multi-GB multichar CSV pairs."""

from pegasus.validation.pipeline.in_memory import should_try_in_memory_reconcile


def test_multichar_pair_skips_in_memory_when_files_are_huge() -> None:
    twenty_gb = 20 * 1024**3
    assert not should_try_in_memory_reconcile(
        enable_in_memory_reconcile=True,
        auto_in_memory_max_bytes=256 * 1024**2,
        source_bytes=twenty_gb,
        target_bytes=twenty_gb,
        memory_budget_bytes=10 * 1024**3,
    )


def test_small_pair_may_use_in_memory_when_enabled() -> None:
    assert should_try_in_memory_reconcile(
        enable_in_memory_reconcile=True,
        auto_in_memory_max_bytes=256 * 1024**2,
        source_bytes=50 * 1024**2,
        target_bytes=50 * 1024**2,
        memory_budget_bytes=10 * 1024**3,
    )
