# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-25T04:45:06Z
# --- END GENERATED FILE METADATA ---

from pegasus.validation.pipeline.live_progress import LiveProgressTracker


def test_live_progress_emits_partition_snapshot() -> None:
    events: list[dict] = []
    tracker = LiveProgressTracker(
        events.append,
        chunk_rows=50_000,
        column_count=18,
        partition_buckets=512,
        est_rows=200_000,
    )
    tracker.begin_partition()
    tracker.side_started("source")
    tracker.on_chunk("source", chunk_index=0, rows_in_chunk=50_000)
    tracker.side_finished("source", total_rows=50_000)

    assert events
    last = events[-1]
    assert last["phase"] == "partitioning"
    assert last["live"] is True
    live = last["progress"]["live"]
    assert live["column_count"] == 18
    assert live["source"]["rows_processed"] == 50_000
    assert live["source"]["chunks_completed"] == 1
    assert last["percent"] is not None


def test_live_progress_reconcile_percent() -> None:
    events: list[dict] = []
    tracker = LiveProgressTracker(
        events.append,
        chunk_rows=10_000,
        column_count=4,
        partition_buckets=100,
        emit_interval_seconds=0.0,
    )
    tracker.begin_reconcile(partitions_total=10, reconcile_workers=4)
    tracker.on_reconcile_done(partitions_done=5)
    last = events[-1]
    assert last["phase"] == "reconciling"
    assert last["progress"]["live"]["reconcile"]["partitions_done"] == 5
    assert last["percent"] == 80.0
