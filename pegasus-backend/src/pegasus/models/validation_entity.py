# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-30T08:29:07Z
# --- END GENERATED FILE METADATA ---

"""ORM model for user-managed validation entities inferred from filenames."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pegasus.core.field_encryption import EncryptedJSON, EncryptedText
from pegasus.models.base import Base


class ValidationEntity(Base):
    """Normalized entity definitions used for filename inference."""

    __tablename__ = "validation_entities"
    __table_args__ = (
        Index("ix_validation_entities_name", "name", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(EncryptedJSON(), nullable=False, default=list)
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
