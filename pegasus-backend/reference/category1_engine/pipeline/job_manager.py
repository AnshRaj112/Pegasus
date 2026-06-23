# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-19T09:48:25Z
# --- END GENERATED FILE METADATA ---

"""Job orchestration and state management."""

import asyncio
import threading
from datetime import datetime, timezone
from typing import Callable, Optional
from uuid import UUID

from category1.config import ReconciliationConfig
from category1.core.reconciliation_engine import ReconciliationEngine
from category1.models.schemas import (
    JobStatus,
    JobSummary,
    ReconciliationJobConfig,
    ReconciliationResult,
)
from category1.readers.base import StreamingReader


class JobManager:
    """Manages reconciliation job lifecycle with in-memory state and async execution."""

    def __init__(self, config: Optional[ReconciliationConfig] = None):
        self.config = config or ReconciliationConfig()
        self._jobs: dict[UUID, ReconciliationResult] = {}
        self._summaries: dict[UUID, JobSummary] = {}
        self._lock = threading.Lock()

    def create_job(self, job_config: ReconciliationJobConfig) -> JobSummary:
        now = datetime.now(timezone.utc)
        summary = JobSummary(
            job_id=job_config.job_id,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._summaries[job_config.job_id] = summary
            self._jobs[job_config.job_id] = ReconciliationResult(
                job_id=job_config.job_id, status=JobStatus.PENDING,
            )
        return summary

    def get_job(self, job_id: UUID) -> Optional[ReconciliationResult]:
        with self._lock:
            return self._jobs.get(job_id)

    def get_summary(self, job_id: UUID) -> Optional[JobSummary]:
        with self._lock:
            return self._summaries.get(job_id)

    def list_jobs(self) -> list[JobSummary]:
        with self._lock:
            return list(self._summaries.values())

    def _update_progress(self, job_id: UUID, status: JobStatus, pct: float, phase: str) -> None:
        with self._lock:
            if job_id in self._summaries:
                s = self._summaries[job_id]
                s.status = status
                s.progress_pct = pct
                s.current_phase = phase
                s.updated_at = datetime.now(timezone.utc)
            if job_id in self._jobs:
                self._jobs[job_id].status = status

    def submit_job(
        self,
        job_config: ReconciliationJobConfig,
        source_reader: Optional[StreamingReader] = None,
        target_reader: Optional[StreamingReader] = None,
    ) -> JobSummary:
        self.create_job(job_config)

        if source_reader is None:
            source_reader = StreamingReader.create(job_config.source)
        if target_reader is None:
            target_reader = StreamingReader.create(job_config.target)

        def run():
            rc = ReconciliationConfig(
                chunk_size=job_config.chunk_size,
                num_partitions=job_config.num_partitions,
                memory_limit_mb=job_config.memory_limit_mb,
                work_dir=self.config.work_dir,
            )
            reconciler = ReconciliationEngine(rc)
            reconciler.set_progress_callback(
                lambda status, pct, phase: self._update_progress(
                    job_config.job_id, status, pct, phase
                )
            )
            try:
                result = reconciler.run(job_config, source_reader, target_reader)
                with self._lock:
                    self._jobs[job_config.job_id] = result
            except Exception as e:
                with self._lock:
                    self._jobs[job_config.job_id].status = JobStatus.FAILED
                    self._jobs[job_config.job_id].error_message = str(e)
                    self._summaries[job_config.job_id].status = JobStatus.FAILED

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return self._summaries[job_config.job_id]

    def cancel_job(self, job_id: UUID) -> bool:
        with self._lock:
            if job_id in self._summaries:
                self._summaries[job_id].status = JobStatus.CANCELLED
                return True
        return False

    def delete_job(self, job_id: UUID) -> bool:
        ReconciliationEngine.cleanup_job(job_id, self.config.work_dir)
        with self._lock:
            self._jobs.pop(job_id, None)
            return self._summaries.pop(job_id, None) is not None
