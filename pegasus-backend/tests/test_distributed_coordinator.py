# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-26T09:50:11Z
# --- END GENERATED FILE METADATA ---

"""Tests for distributed coordinator aggregation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from pegasus.validation.workers.coordinator import (
    RESULT_QUEUE_PREFIX,
    DistributedReconciliationCoordinator,
)


def test_reconcile_partitions_aggregates_stats() -> None:
    work = Path("/tmp/work")
    coord = DistributedReconciliationCoordinator(redis_url="redis://localhost:6379/0", work_dir=work)
    mock_redis = MagicMock()
    coord._client = mock_redis

    mock_redis.delete.return_value = 1
    with patch.object(coord, "enqueue_partitions", return_value=2):
        mock_redis.brpop.side_effect = [
            (
                RESULT_QUEUE_PREFIX + "job1",
                json.dumps({"stats": {"missing": 1, "extra": 0, "changed": 2, "matching": 10}}),
            ),
            (
                RESULT_QUEUE_PREFIX + "job1",
                json.dumps({"stats": {"missing": 0, "extra": 1, "changed": 0, "matching": 5}}),
            ),
        ]
        result = coord.reconcile_partitions("job1", [0, 1], timeout_seconds=10)

    assert result == (1, 1, 2, 15, 2)


def test_should_use_requires_redis() -> None:
    with patch.object(DistributedReconciliationCoordinator, "available", return_value=False):
        assert not DistributedReconciliationCoordinator.should_use(
            enabled=True,
            redis_url="redis://x",
            combined_bytes=20 * 1024**3,
            min_bytes=10 * 1024**3,
        )
