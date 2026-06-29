# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T07:09:43Z
# --- END GENERATED FILE METADATA ---

"""Distributed reconciliation engine with external-memory partition processing."""

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID

from category1.config import ReconciliationConfig
from category1.core.canonicalization import CanonicalizationEngine
from category1.core.external_memory import MemoryMonitor
from category1.core.fingerprint import FingerprintEngine
from category1.core.mismatch_detector import MismatchDetector
from category1.core.partitioner import PartitionWriter, StreamingPartitioner
from category1.core.schema_validator import SchemaValidator
from category1.models.schemas import (
    ExecutionStats,
    JobStatus,
    MismatchRecord,
    PartitionStats,
    ReconciliationJobConfig,
    ReconciliationResult,
    SchemaValidationResult,
)
from category1.readers.base import StreamingReader
from category1.reporting.report_generator import ReportGenerator


class ReconciliationEngine:
    """
    Orchestrates the full reconciliation pipeline:
    Schema → Row Count → Partition → Reconcile → Drilldown → Report
    """

    def __init__(self, config: Optional[ReconciliationConfig] = None):
        self.config = config or ReconciliationConfig()
        self._progress_callback: Optional[Callable[[JobStatus, float, str], None]] = None

    def set_progress_callback(self, cb: Callable[[JobStatus, float, str], None]) -> None:
        self._progress_callback = cb

    def _emit_progress(self, status: JobStatus, pct: float, phase: str) -> None:
        if self._progress_callback:
            self._progress_callback(status, pct, phase)

    def run(
        self,
        job_config: ReconciliationJobConfig,
        source_reader: StreamingReader,
        target_reader: StreamingReader,
    ) -> ReconciliationResult:
        job_id = job_config.job_id
        work_dir = self.config.work_dir / str(job_id)
        work_dir.mkdir(parents=True, exist_ok=True)

        memory_monitor = MemoryMonitor(
            job_config.memory_limit_mb,
            self.config.spill_threshold_pct,
        )
        exec_stats = ExecutionStats(start_time=datetime.now(timezone.utc))

        result = ReconciliationResult(job_id=job_id, status=JobStatus.PENDING)

        try:
            # Phase 1: Schema Validation
            self._emit_progress(JobStatus.SCHEMA_VALIDATION, 5, "Validating schemas")
            result.status = JobStatus.SCHEMA_VALIDATION
            source_schema = source_reader.get_schema()
            target_schema = target_reader.get_schema()
            validator = SchemaValidator(job_config.column_mapping)
            schema_result = validator.validate(source_schema, target_schema)
            result.schema_validation = schema_result

            compare_columns = job_config.compare_columns or source_schema.column_names()
            key_columns = job_config.key_columns or compare_columns[:1]
            column_types = {c.name: c.data_type for c in source_schema.columns}

            canonicalizer = CanonicalizationEngine(overrides=job_config.canonicalization)
            fp_engine = FingerprintEngine(canonicalizer)

            # Phase 2: Row Count (cheap metadata only)
            if job_config.enable_row_count:
                result.source_row_count = source_schema.row_count or source_reader.get_row_count()
                result.target_row_count = target_schema.row_count or target_reader.get_row_count()

            self._emit_progress(JobStatus.PARTITIONING_SOURCE, 15, "Partitioning source")

            # Phase 3: Stream partition source
            result.status = JobStatus.PARTITIONING_SOURCE
            source_partitioner = StreamingPartitioner(
                fp_engine, key_columns, compare_columns,
                job_config.num_partitions, job_config.key_strategy,
                job_config.column_mapping, column_types,
            )
            source_writer = PartitionWriter(work_dir, "source", job_config.num_partitions)
            exec_stats.source_rows_processed = self._stream_and_partition(
                source_reader, source_partitioner, source_writer, job_config.chunk_size, exec_stats
            )
            source_counts = source_writer.close()

            self._emit_progress(JobStatus.PARTITIONING_TARGET, 40, "Partitioning target")

            # Phase 3b: Stream partition target
            result.status = JobStatus.PARTITIONING_TARGET
            target_writer = PartitionWriter(work_dir, "target", job_config.num_partitions)
            exec_stats.target_rows_processed = self._stream_and_partition(
                target_reader,
                source_partitioner, target_writer, job_config.chunk_size, exec_stats,
            )
            target_counts = target_writer.close()

            self._emit_progress(JobStatus.RECONCILING, 55, "Reconciling partitions")

            # Phase 4: Partition reconciliation
            result.status = JobStatus.RECONCILING
            detector = MismatchDetector(
                compare_columns, job_config.column_mapping, column_types,
                job_config.enable_column_drilldown, self.config.sample_mismatch_limit,
            )

            all_mismatches: list[MismatchRecord] = []
            active_partitions = set(source_counts.keys()) | set(target_counts.keys())

            for i, pid in enumerate(sorted(active_partitions)):
                src_path = source_writer.get_partition_path(pid)
                tgt_path = target_writer.get_partition_path(pid)
                if not src_path.exists() and not tgt_path.exists():
                    continue

                spill_dir = work_dir / "spill" / f"part_{pid:05d}"
                pstats, mismatches = detector.reconcile_partition(
                    src_path, tgt_path, pid, spill_dir, memory_monitor,
                )
                result.partition_stats.append(pstats)
                result.missing_count += pstats.missing
                result.extra_count += pstats.extra
                result.mismatched_count += pstats.mismatched
                all_mismatches.extend(mismatches)
                exec_stats.partitions_processed += 1

                pct = 55 + (40 * (i + 1) / max(len(active_partitions), 1))
                self._emit_progress(JobStatus.RECONCILING, pct, f"Partition {pid}")

            result.matching_count = (
                min(exec_stats.source_rows_processed, exec_stats.target_rows_processed)
                - result.mismatched_count
            )
            result.sample_mismatches = all_mismatches[: self.config.sample_mismatch_limit]

            # Phase 5: Reporting
            self._emit_progress(JobStatus.REPORTING, 95, "Generating report")
            result.status = JobStatus.REPORTING
            exec_stats.end_time = datetime.now(timezone.utc)
            exec_stats.duration_seconds = (
                exec_stats.end_time - exec_stats.start_time
            ).total_seconds()
            exec_stats.peak_memory_mb = memory_monitor.peak_mb
            exec_stats.disk_spill_mb = memory_monitor.spill_mb
            result.execution_stats = exec_stats

            report_gen = ReportGenerator(work_dir / "reports")
            report_gen.generate(result, job_config)

            result.status = JobStatus.COMPLETED
            self._emit_progress(JobStatus.COMPLETED, 100, "Complete")

        except Exception as e:
            result.status = JobStatus.FAILED
            result.error_message = str(e)
            self._emit_progress(JobStatus.FAILED, 0, str(e))
            raise
        finally:
            if self.config.storage_backend.value == "local":
                pass  # retain for inspection; cleanup via job API

        return result

    def _stream_and_partition(
        self,
        reader: StreamingReader,
        partitioner: StreamingPartitioner,
        writer: PartitionWriter,
        chunk_size: int,
        exec_stats: ExecutionStats,
    ) -> int:
        total = 0
        for chunk in reader.read_chunks(chunk_size):
            count = partitioner.process_chunk(chunk, writer)
            total += count
            exec_stats.chunks_processed += 1
        return total

    @staticmethod
    def cleanup_job(job_id: UUID, work_dir: Optional[Path] = None) -> None:
        base = work_dir or ReconciliationConfig().work_dir
        job_path = base / str(job_id)
        if job_path.exists():
            shutil.rmtree(job_path, ignore_errors=True)
