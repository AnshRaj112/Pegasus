# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T12:00:00Z
# --- END GENERATED FILE METADATA ---

"""Optional Redis-backed validation job dispatch for multi-replica / Kubernetes deployments."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pegasus.core.config import Settings

logger = logging.getLogger(__name__)

_QUEUE_KEY = "pegasus:validation:pending"
_INFLIGHT_KEY = "pegasus:validation:inflight"


class DistributedQueueBackend(Protocol):
    def enqueue(self, job_id: uuid.UUID, job_dir: Path) -> None: ...

    def dequeue_blocking(self, timeout_seconds: int = 5) -> tuple[uuid.UUID, Path] | None: ...

    def ack(self, job_id: uuid.UUID) -> None: ...


class InProcessDistributedQueue:
    """No-op backend: jobs stay on the local ValidationJobQueue."""

    def enqueue(self, job_id: uuid.UUID, job_dir: Path) -> None:
        return

    def dequeue_blocking(self, timeout_seconds: int = 5) -> tuple[uuid.UUID, Path] | None:
        return None

    def ack(self, job_id: uuid.UUID) -> None:
        return


class RedisDistributedQueue:
    """Minimal Redis LIST queue for external worker pods."""

    def __init__(self, url: str, *, jobs_root: Path) -> None:
        import redis

        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._jobs_root = jobs_root

    def enqueue(self, job_id: uuid.UUID, job_dir: Path) -> None:
        self._client.rpush(_QUEUE_KEY, f"{job_id}|{job_dir.resolve()}")

    def dequeue_blocking(self, timeout_seconds: int = 5) -> tuple[uuid.UUID, Path] | None:
        item = self._client.blpop(_QUEUE_KEY, timeout=timeout_seconds)
        if not item:
            return None
        _, payload = item
        job_id_str, job_dir_str = payload.split("|", 1)
        job_id = uuid.UUID(job_id_str)
        self._client.hset(_INFLIGHT_KEY, str(job_id), job_dir_str)
        return job_id, Path(job_dir_str)

    def ack(self, job_id: uuid.UUID) -> None:
        self._client.hdel(_INFLIGHT_KEY, str(job_id))


_backend: DistributedQueueBackend | None = None


def get_distributed_queue(settings: Settings) -> DistributedQueueBackend:
    global _backend
    if _backend is not None:
        return _backend
    url = (settings.validation_distributed_queue_url or "").strip()
    if not url:
        _backend = InProcessDistributedQueue()
        return _backend
    from pegasus.services.validation_helpers import validation_jobs_root

    try:
        _backend = RedisDistributedQueue(url, jobs_root=validation_jobs_root(settings))
        logger.info("Using Redis distributed validation queue at %s", url.split("@")[-1])
    except Exception:
        logger.exception("Failed to connect Redis queue; falling back to in-process queue")
        _backend = InProcessDistributedQueue()
    return _backend


def reset_distributed_queue() -> None:
    global _backend
    _backend = None
