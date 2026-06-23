# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-23T05:34:17Z
# --- END GENERATED FILE METADATA ---

"""ORM model for saved cloud storage connections."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from pegasus.core.field_encryption import EncryptedText
from pegasus.models.base import Base


class CloudConnection(Base):
    """Reusable admin-managed cloud credential profile."""

    __tablename__ = "cloud_connections"
    __table_args__ = (
        Index("ix_cloud_connections_name", "name", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="google-cloud-storage")
    bucket: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    project_id: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    credentials_json: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
