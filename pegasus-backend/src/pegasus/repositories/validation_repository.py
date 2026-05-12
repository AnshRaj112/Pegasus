"""Persistence helpers for validation runs and mismatch rows (async SQLAlchemy 2.0)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pegasus.models import MismatchReport, ValidationRun
from pegasus.models.enums import ValidationRunStatus
from pegasus.services.validation_service import ValidationRunResult
from pegasus.validation.comparators.models import MismatchType

logger = logging.getLogger(__name__)


class ValidationRunRepository:
    """Create and update :class:`ValidationRun` rows and related :class:`MismatchReport` rows."""

    @staticmethod
    async def create_running(
        session: AsyncSession,
        *,
        source_filename: str | None,
        target_filename: str | None,
        uid_column: str,
        delimiter: str,
    ) -> ValidationRun:
        """Insert a new run in ``RUNNING`` state with ``started_at`` set."""
        now = datetime.now(UTC)
        run = ValidationRun(
            status=ValidationRunStatus.RUNNING,
            source_filename=source_filename,
            target_filename=target_filename,
            uid_column=uid_column,
            delimiter=delimiter,
            started_at=now,
        )
        session.add(run)
        await session.flush()
        logger.info("Created validation run id=%s status=running", run.id)
        return run

    @staticmethod
    async def mark_failed(
        session: AsyncSession,
        run_id: uuid.UUID,
        *,
        detail: str,
    ) -> None:
        """Set run to ``FAILED`` and store ``error_detail``."""
        run = await session.get(ValidationRun, run_id)
        if run is None:
            logger.warning("mark_failed: validation run %s not found", run_id)
            return
        run.status = ValidationRunStatus.FAILED
        run.error_detail = detail[:16_000]
        run.completed_at = datetime.now(UTC)
        run.updated_at = datetime.now(UTC)
        logger.info("Marked validation run id=%s as failed", run_id)

    @staticmethod
    async def complete_success(
        session: AsyncSession,
        run_id: uuid.UUID,
        result: ValidationRunResult,
    ) -> None:
        """Update aggregates and insert all mismatch rows from the Polars report."""
        run = await session.get(ValidationRun, run_id)
        if run is None:
            logger.warning("complete_success: validation run %s not found", run_id)
            return

        summary = result.report.summary
        mismatches = result.report.mismatches
        artifact = result.mismatch_artifact_path or result.report.mismatch_artifact_path

        total_mismatch = (
            int(summary.get(MismatchType.MISSING_IN_TARGET.value, 0))
            + int(summary.get(MismatchType.EXTRA_IN_TARGET.value, 0))
            + int(summary.get(MismatchType.VALUE_MISMATCH.value, 0))
        )

        run.status = ValidationRunStatus.COMPLETED
        run.missing_in_target_count = int(summary.get(MismatchType.MISSING_IN_TARGET.value, 0))
        run.extra_in_target_count = int(summary.get(MismatchType.EXTRA_IN_TARGET.value, 0))
        run.value_mismatch_count = int(summary.get(MismatchType.VALUE_MISMATCH.value, 0))
        run.total_mismatch_records = total_mismatch
        run.source_row_count = result.source_row_count
        run.target_row_count = result.target_row_count
        run.compared_column_count = result.compared_column_count
        run.is_match = total_mismatch == 0
        run.completed_at = datetime.now(UTC)
        run.updated_at = datetime.now(UTC)
        run.error_detail = None

        if total_mismatch > 0 and artifact is not None and artifact.is_file():
            p = Path(artifact)
            batch_orm: list[MismatchReport] = []
            batch_size = 2_000
            with p.open(encoding="utf-8") as fp:
                for line in fp:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    batch_orm.append(
                        MismatchReport(
                            validation_run_id=run_id,
                            uid=str(r.get("uid") or ""),
                            mismatch_type=str(r.get("mismatch_type") or ""),
                            column_name=_optional_str(r.get("column_name")),
                            source_value=_optional_str(r.get("source_value")),
                            target_value=_optional_str(r.get("target_value")),
                            row_detail=_optional_str(r.get("row_detail")),
                        )
                    )
                    if len(batch_orm) >= batch_size:
                        session.add_all(batch_orm)
                        await session.flush()
                        batch_orm.clear()
            if batch_orm:
                session.add_all(batch_orm)
                await session.flush()
        elif mismatches.height > 0:
            rows = mismatches.to_dicts()
            batch_size = 2_000
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                session.add_all(
                    [
                        MismatchReport(
                            validation_run_id=run_id,
                            uid=str(r.get("uid") or ""),
                            mismatch_type=str(r.get("mismatch_type") or ""),
                            column_name=_optional_str(r.get("column_name")),
                            source_value=_optional_str(r.get("source_value")),
                            target_value=_optional_str(r.get("target_value")),
                            row_detail=_optional_str(r.get("row_detail")),
                        )
                        for r in batch
                    ]
                )
                await session.flush()

        await session.flush()
        logger.info(
            "Completed validation run id=%s mismatches_stored=%d",
            run_id,
            total_mismatch,
        )

    @staticmethod
    async def get_run(session: AsyncSession, run_id: uuid.UUID) -> ValidationRun | None:
        """Load a run by primary key."""
        return await session.get(ValidationRun, run_id)

    @staticmethod
    async def list_recent(session: AsyncSession, *, limit: int = 20) -> list[ValidationRun]:
        """Return latest runs by ``created_at`` (newest first)."""
        stmt = select(ValidationRun).order_by(ValidationRun.created_at.desc()).limit(limit)
        result = await session.scalars(stmt)
        return list(result.all())


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
