# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T08:29:07Z
# --- END GENERATED FILE METADATA ---

"""Persistence helpers for validation runs and mismatch rows (async SQLAlchemy 2.0)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pegasus.core.file_pair import compute_file_pair_key
from pegasus.models import MismatchReport, ValidationRun
from pegasus.models.enums import ValidationRunStatus
from pegasus.services.validation_service import ValidationRunDurations, ValidationRunResult
from pegasus.validation.comparators.models import MismatchType, VALUE_MISMATCH_ROWS_SUMMARY_KEY
from pegasus.validation.test_mode_policy import validation_run_is_match
from pegasus.core.delimiter_tokens import normalize_delimiter_for_storage

logger = logging.getLogger(__name__)


def _value_mismatch_row_count(*, mismatches, artifact: Path | None) -> int:
    """Count distinct UIDs with at least one value_mismatch record."""
    mtype = MismatchType.VALUE_MISMATCH.value
    uids: set[str] = set()
    if mismatches is not None and getattr(mismatches, "height", 0) > 0:
        for row in mismatches.to_dicts():
            if row.get("mismatch_type") == mtype:
                uid = str(row.get("uid") or "")
                if uid:
                    uids.add(uid)
    if not uids and artifact is not None and artifact.is_file():
        with artifact.open(encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("mismatch_type") == mtype:
                    uid = str(record.get("uid") or "")
                    if uid:
                        uids.add(uid)
    return len(uids)


def _artifact_has_rows(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


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
        source_path: str | None = None,
        target_path: str | None = None,
        file_pair_key: str | None = None,
        column_mappings: list[dict[str, Any]] | None = None,
        validate_header_formats: bool = False,
        validate_footers: bool = False,
    ) -> ValidationRun:
        """Insert a new run in ``RUNNING`` state with ``started_at`` set."""
        now = datetime.now(UTC)
        src = (source_path or source_filename or "").strip() or None
        tgt = (target_path or target_filename or "").strip() or None
        pair_key = file_pair_key
        if pair_key is None and src and tgt:
            pair_key = compute_file_pair_key(src, tgt)
        run = ValidationRun(
            status=ValidationRunStatus.RUNNING,
            source_filename=source_filename,
            target_filename=target_filename,
            source_path=source_path,
            target_path=target_path,
            file_pair_key=pair_key,
            uid_column=uid_column,
            delimiter=normalize_delimiter_for_storage(delimiter),
            column_mappings=column_mappings or [],
            validate_header_formats=validate_header_formats,
            validate_footers=validate_footers,
            started_at=now,
        )
        session.add(run)
        await session.flush()
        logger.info("Created validation run id=%s status=running pair_key=%s", run.id, pair_key)
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
        *,
        column_mappings: list[dict[str, Any]] | None = None,
        max_mismatch_rows: int = 0,
        job_meta: dict[str, Any] | None = None,
    ) -> None:
        """Update aggregates and optionally insert mismatch rows from the Polars report."""
        run = await session.get(ValidationRun, run_id)
        if run is None:
            logger.warning("complete_success: validation run %s not found", run_id)
            return

        summary = result.report.summary
        mismatches = result.report.mismatches
        artifact_raw = result.mismatch_artifact_path or result.report.mismatch_artifact_path
        artifact_path = Path(artifact_raw).expanduser() if artifact_raw is not None else None

        total_mismatch = (
            int(summary.get(MismatchType.MISSING_IN_TARGET.value, 0))
            + int(summary.get(MismatchType.EXTRA_IN_TARGET.value, 0))
            + int(summary.get(MismatchType.VALUE_MISMATCH.value, 0))
        )

        run.status = ValidationRunStatus.COMPLETED
        run.missing_in_target_count = int(summary.get(MismatchType.MISSING_IN_TARGET.value, 0))
        run.extra_in_target_count = int(summary.get(MismatchType.EXTRA_IN_TARGET.value, 0))
        run.value_mismatch_count = int(summary.get(MismatchType.VALUE_MISMATCH.value, 0))
        value_mismatch_rows = int(summary.get(VALUE_MISMATCH_ROWS_SUMMARY_KEY, 0))
        if value_mismatch_rows <= 0:
            value_mismatch_rows = _value_mismatch_row_count(
                mismatches=mismatches,
                artifact=artifact_path if artifact_path and artifact_path.is_file() else None,
            )
        run.value_mismatch_row_count = value_mismatch_rows
        run.total_mismatch_records = total_mismatch
        run.source_row_count = result.source_row_count
        run.target_row_count = result.target_row_count
        run.compared_column_count = result.compared_column_count
        run.compared_columns = list(result.compared_columns)
        run.is_match = validation_run_is_match(
            summary,
            total_mismatch_records=total_mismatch,
            test_mode=result.test_mode,
            source_row_count=result.source_row_count,
            target_row_count=result.target_row_count,
        )
        run.completed_at = datetime.now(UTC)
        run.updated_at = datetime.now(UTC)
        run.error_detail = None

        footer_blob = dict(run.footer_validation or {})
        if result.footer_validation:
            footer_blob.update(dict(result.footer_validation))
        if result.test_mode:
            footer_blob["test_mode"] = str(result.test_mode)
        if result.litmus:
            footer_blob["litmus"] = dict(result.litmus)
        run.footer_validation = footer_blob

        if column_mappings is not None:
            run.column_mappings = column_mappings
        if result.mapping_format_checks is not None:
            run.mapping_format_checks = list(result.mapping_format_checks)

        if result.durations is not None:
            run.upload_duration_seconds = result.durations.upload_seconds
            run.validation_duration_seconds = result.durations.validation_seconds
            run.total_duration_seconds = result.durations.total_seconds

        persist_rows = total_mismatch > 0
        if max_mismatch_rows > 0 and total_mismatch > max_mismatch_rows:
            logger.info(
                "Skipping mismatch row persistence for run %s: %d rows exceeds cap %d",
                run_id,
                total_mismatch,
                max_mismatch_rows,
            )
            persist_rows = False
            if artifact_path is not None and artifact_path.is_file():
                existing_footer = dict(run.footer_validation or {})
                persistence = dict(existing_footer.get("_persistence") or {})
                persistence.update(
                    {
                        "mismatch_rows_persisted": False,
                        "mismatch_artifact_path": str(artifact_path),
                        "mismatch_row_cap": max_mismatch_rows,
                    }
                )
                existing_footer["_persistence"] = persistence
                run.footer_validation = existing_footer

        if artifact_path is not None and _artifact_has_rows(artifact_path):
            existing_footer = dict(run.footer_validation or {})
            persistence = dict(existing_footer.get("_persistence") or {})
            persistence["mismatch_artifact_path"] = str(artifact_path)
            job_id = (job_meta or {}).get("job_id")
            if job_id:
                persistence["validation_job_id"] = str(job_id)
            existing_footer["_persistence"] = persistence
            run.footer_validation = existing_footer

        rows_persisted = 0
        if persist_rows and artifact_path is not None and _artifact_has_rows(artifact_path):
            p = artifact_path
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
                    rows_persisted += 1
                    if len(batch_orm) >= batch_size:
                        session.add_all(batch_orm)
                        await session.flush()
                        batch_orm.clear()
            if batch_orm:
                session.add_all(batch_orm)
                await session.flush()
        if persist_rows and rows_persisted == 0 and mismatches.height > 0:
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
            rows_persisted = len(rows)

        if persist_rows and rows_persisted == 0 and mismatches.height <= 0:
            logger.warning(
                "Validation run %s has %d mismatch records but no rows were persisted "
                "(artifact=%s mismatches_frame=%d)",
                run_id,
                total_mismatch,
                artifact_path,
                mismatches.height,
            )

        if artifact_path is not None and _artifact_has_rows(artifact_path):
            existing_footer = dict(run.footer_validation or {})
            persistence = dict(existing_footer.get("_persistence") or {})
            persistence["mismatch_rows_persisted"] = rows_persisted > 0
            persistence["mismatch_artifact_path"] = str(artifact_path)
            job_id = (job_meta or {}).get("job_id")
            if job_id:
                persistence["validation_job_id"] = str(job_id)
            existing_footer["_persistence"] = persistence
            run.footer_validation = existing_footer

        await session.flush()
        logger.info(
            "Completed validation run id=%s mismatches_stored=%d rows_persisted=%d",
            run_id,
            total_mismatch,
            rows_persisted if persist_rows else 0,
        )

    @staticmethod
    async def get_run(session: AsyncSession, run_id: uuid.UUID) -> ValidationRun | None:
        """Load a run by primary key."""
        return await session.get(ValidationRun, run_id)

    @staticmethod
    def _apply_status_filter(stmt, statuses: list[ValidationRunStatus] | None):
        if statuses:
            stmt = stmt.where(ValidationRun.status.in_(statuses))
        return stmt

    @staticmethod
    async def list_recent(
        session: AsyncSession,
        *,
        limit: int = 20,
        offset: int = 0,
        file_pair_key: str | None = None,
        statuses: list[ValidationRunStatus] | None = None,
    ) -> list[ValidationRun]:
        """Return latest runs by ``created_at`` (newest first)."""
        stmt = select(ValidationRun).order_by(ValidationRun.created_at.desc())
        if file_pair_key:
            stmt = stmt.where(ValidationRun.file_pair_key == file_pair_key)
        stmt = ValidationRunRepository._apply_status_filter(stmt, statuses)
        stmt = stmt.offset(offset).limit(limit)
        result = await session.scalars(stmt)
        return list(result.all())

    @staticmethod
    async def daily_completed_stats(
        session: AsyncSession,
        *,
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, int, int]]:
        """Group terminal runs by calendar day of ``completed_at`` (UTC bucket)."""
        day_bucket = func.date_trunc("day", ValidationRun.completed_at).label("day_bucket")
        passed = func.sum(
            case(
                (
                    and_(
                        ValidationRun.status == ValidationRunStatus.COMPLETED,
                        ValidationRun.is_match.is_(True),
                    ),
                    1,
                ),
                else_=0,
            )
        )
        failed = func.sum(
            case(
                (
                    or_(
                        ValidationRun.status == ValidationRunStatus.FAILED,
                        and_(
                            ValidationRun.status == ValidationRunStatus.COMPLETED,
                            or_(
                                ValidationRun.is_match.is_(False),
                                ValidationRun.is_match.is_(None),
                            ),
                        ),
                    ),
                    1,
                ),
                else_=0,
            )
        )
        stmt = (
            select(day_bucket, passed, failed)
            .where(ValidationRun.completed_at.isnot(None))
            .where(ValidationRun.completed_at >= start)
            .where(ValidationRun.completed_at < end)
            .group_by(day_bucket)
            .order_by(day_bucket)
        )
        rows = await session.execute(stmt)
        out: list[tuple[datetime, int, int]] = []
        for bucket, p, f in rows.all():
            out.append((bucket, int(p or 0), int(f or 0)))
        return out

    @staticmethod
    async def hourly_completed_stats(
        session: AsyncSession,
        *,
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, int, int]]:
        """Group terminal runs by hour of ``completed_at`` (UTC bucket)."""
        hour_bucket = func.date_trunc("hour", ValidationRun.completed_at).label("hour_bucket")
        passed = func.sum(
            case(
                (
                    and_(
                        ValidationRun.status == ValidationRunStatus.COMPLETED,
                        ValidationRun.is_match.is_(True),
                    ),
                    1,
                ),
                else_=0,
            )
        )
        failed = func.sum(
            case(
                (
                    or_(
                        ValidationRun.status == ValidationRunStatus.FAILED,
                        and_(
                            ValidationRun.status == ValidationRunStatus.COMPLETED,
                            or_(
                                ValidationRun.is_match.is_(False),
                                ValidationRun.is_match.is_(None),
                            ),
                        ),
                    ),
                    1,
                ),
                else_=0,
            )
        )
        stmt = (
            select(hour_bucket, passed, failed)
            .where(ValidationRun.completed_at.isnot(None))
            .where(ValidationRun.completed_at >= start)
            .where(ValidationRun.completed_at < end)
            .group_by(hour_bucket)
            .order_by(hour_bucket)
        )
        rows = await session.execute(stmt)
        out: list[tuple[datetime, int, int]] = []
        for bucket, p, f in rows.all():
            out.append((bucket, int(p or 0), int(f or 0)))
        return out

    @staticmethod
    async def count_runs(
        session: AsyncSession,
        *,
        file_pair_key: str | None = None,
        statuses: list[ValidationRunStatus] | None = None,
    ) -> int:
        """Count runs optionally filtered by file pair."""
        stmt = select(func.count()).select_from(ValidationRun)
        if file_pair_key:
            stmt = stmt.where(ValidationRun.file_pair_key == file_pair_key)
        stmt = ValidationRunRepository._apply_status_filter(stmt, statuses)
        total = await session.scalar(stmt)
        return int(total or 0)

    @staticmethod
    async def count_mismatch_reports(session: AsyncSession, run_id: uuid.UUID) -> int:
        """Return how many mismatch rows are stored for a run."""
        stmt = (
            select(func.count())
            .select_from(MismatchReport)
            .where(MismatchReport.validation_run_id == run_id)
        )
        return int(await session.scalar(stmt) or 0)

    @staticmethod
    async def list_mismatches(
        session: AsyncSession,
        run_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
        mismatch_type: str | None = None,
    ) -> tuple[list[MismatchReport], int]:
        """Return mismatch rows for a run and total count."""
        filters = [MismatchReport.validation_run_id == run_id]
        if mismatch_type:
            filters.append(MismatchReport.mismatch_type == mismatch_type)
        count_stmt = select(func.count()).select_from(MismatchReport).where(*filters)
        total = int(await session.scalar(count_stmt) or 0)
        stmt = (
            select(MismatchReport)
            .where(*filters)
            .order_by(MismatchReport.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = list((await session.scalars(stmt)).all())
        return rows, total

    @staticmethod
    async def delete_run(session: AsyncSession, run_id: uuid.UUID) -> bool:
        """Delete a run by id. Returns True if deleted, False if not found."""
        run = await session.get(ValidationRun, run_id)
        if run is None:
            return False
        await session.delete(run)
        await session.flush()
        return True

    @staticmethod
    async def delete_runs_by_file_pair_key(
        session: AsyncSession,
        pair_key: str | None,
    ) -> int:
        """Delete all validation runs sharing a precomputed ``file_pair_key``."""
        if not pair_key:
            return 0
        stmt = select(ValidationRun).where(ValidationRun.file_pair_key == pair_key)
        result = await session.scalars(stmt)
        runs = list(result.all())
        count = len(runs)
        for run in runs:
            await session.delete(run)
        await session.flush()
        return count

    @staticmethod
    async def delete_runs_by_file_pair(
        session: AsyncSession,
        source_path: str,
        target_path: str,
    ) -> int:
        """Delete all validation runs for a specific source and target file pair."""
        pair_key = compute_file_pair_key(source_path, target_path)
        return await ValidationRunRepository.delete_runs_by_file_pair_key(session, pair_key)

    @staticmethod
    async def delete_all_runs(session: AsyncSession) -> int:
        """Delete all validation runs from the database."""
        stmt = select(ValidationRun)
        result = await session.scalars(stmt)
        runs = list(result.all())
        count = len(runs)
        for run in runs:
            await session.delete(run)
        await session.flush()
        return count




def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
