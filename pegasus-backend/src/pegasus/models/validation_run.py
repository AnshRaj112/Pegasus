# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-07-02T06:35:41Z
# --- END GENERATED FILE METADATA ---

"""ORM model for a validation execution stored in PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pegasus.core.field_encryption import EncryptedJSON, EncryptedText
from pegasus.models.base import Base
from pegasus.models.enums import ValidationRunStatus

if TYPE_CHECKING:
    from pegasus.models.mismatch_report import MismatchReport


class ValidationRun(Base):
    """One end-to-end CSV comparison run (metadata + aggregate mismatch stats)."""

    __tablename__ = "validation_runs"
    __table_args__ = (
        Index("ix_validation_runs_file_pair_key_created_at", "file_pair_key", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    status: Mapped[ValidationRunStatus] = mapped_column(
        SAEnum(
            ValidationRunStatus,
            native_enum=False,
            length=32,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=ValidationRunStatus.PENDING,
    )

    source_filename: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    target_filename: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    source_path: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    target_path: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    file_pair_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uid_column: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    delimiter: Mapped[str] = mapped_column(EncryptedText(), nullable=False, default=",")

    column_mappings: Mapped[list | None] = mapped_column(EncryptedJSON(), nullable=False, default=list)
    compared_columns: Mapped[list | None] = mapped_column(EncryptedJSON(), nullable=True)
    mapping_format_checks: Mapped[list | None] = mapped_column(EncryptedJSON(), nullable=True)
    footer_validation: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    validate_header_formats: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validate_footers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    upload_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    missing_in_target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_in_target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    value_mismatch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    value_mismatch_row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_mismatch_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compared_column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    error_detail: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    mismatch_reports: Mapped[list[MismatchReport]] = relationship(
        "MismatchReport",
        back_populates="validation_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
