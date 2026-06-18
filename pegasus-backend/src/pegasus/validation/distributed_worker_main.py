#!/usr/bin/env python3
"""Standalone validation worker for Kubernetes (BRPOP from Redis distributed queue)."""

from __future__ import annotations

import logging
import sys
import time

from pegasus.core.config import get_settings
from pegasus.services.distributed_validation_queue import (
    InProcessDistributedQueue,
    get_distributed_queue,
)
from pegasus.services.worker_runtime_admission import should_defer_job
from pegasus.validation.job_worker import run_job_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("pegasus.distributed_worker")

_DEFER_SLEEP_SECONDS = 15


def main() -> int:
    settings = get_settings()
    queue = get_distributed_queue(settings)
    if isinstance(queue, InProcessDistributedQueue):
        logger.error(
            "PEGASUS_VALIDATION_DISTRIBUTED_QUEUE_URL is not set; "
            "this entrypoint requires a Redis-backed queue."
        )
        return 2

    logger.info("Distributed validation worker started")
    while True:
        item = queue.dequeue_blocking(timeout_seconds=30)
        if item is None:
            continue
        job_id, job_dir = item
        defer, reason = should_defer_job(job_dir, settings)
        if defer:
            logger.info("Deferring job %s: %s", job_id, reason)
            queue.requeue(job_id, job_dir)
            time.sleep(_DEFER_SLEEP_SECONDS)
            continue
        logger.info("Running job %s from %s", job_id, job_dir)
        rc = run_job_directory(job_dir)
        queue.ack(job_id)
        logger.info("Job %s finished rc=%s", job_id, rc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
