# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T05:22:13Z
# --- END GENERATED FILE METADATA ---

"""ORM model for individual mismatch rows linked to a :class:`ValidationRun`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pegasus.core.field_encryption import EncryptedText
from pegasus.models.base import Base

if TYPE_CHECKING:
    from pegasus.models.validation_run import ValidationRun


class MismatchReport(Base):
    """One long-form mismatch record (uid + type + optional column diff)."""

    __tablename__ = "mismatch_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    validation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uid: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    mismatch_type: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    column_name: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    source_value: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    target_value: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    row_detail: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    validation_run: Mapped[ValidationRun] = relationship(
        "ValidationRun",
        back_populates="mismatch_reports",
    )
