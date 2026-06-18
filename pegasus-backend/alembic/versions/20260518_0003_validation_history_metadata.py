# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Add mapping, durations, and file-pair metadata to validation_runs.

Revision ID: 20260518_0003
Revises: 20260511_0002
Create Date: 2026-05-18

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260518_0003"
down_revision: Union[str, Sequence[str], None] = "20260511_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("validation_runs", sa.Column("source_path", sa.Text(), nullable=True))
    op.add_column("validation_runs", sa.Column("target_path", sa.Text(), nullable=True))
    op.add_column("validation_runs", sa.Column("file_pair_key", sa.String(length=64), nullable=True))
    op.add_column(
        "validation_runs",
        sa.Column(
            "column_mappings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("validation_runs", sa.Column("compared_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "validation_runs",
        sa.Column("mapping_format_checks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "validation_runs",
        sa.Column("footer_validation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "validation_runs",
        sa.Column("validate_header_formats", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "validation_runs",
        sa.Column("validate_footers", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("validation_runs", sa.Column("upload_duration_seconds", sa.Float(), nullable=True))
    op.add_column("validation_runs", sa.Column("validation_duration_seconds", sa.Float(), nullable=True))
    op.add_column("validation_runs", sa.Column("total_duration_seconds", sa.Float(), nullable=True))
    op.create_index("ix_validation_runs_file_pair_key", "validation_runs", ["file_pair_key"], unique=False)
    op.create_index(
        "ix_validation_runs_file_pair_key_created_at",
        "validation_runs",
        ["file_pair_key", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_validation_runs_file_pair_key_created_at", table_name="validation_runs")
    op.drop_index("ix_validation_runs_file_pair_key", table_name="validation_runs")
    op.drop_column("validation_runs", "total_duration_seconds")
    op.drop_column("validation_runs", "validation_duration_seconds")
    op.drop_column("validation_runs", "upload_duration_seconds")
    op.drop_column("validation_runs", "validate_footers")
    op.drop_column("validation_runs", "validate_header_formats")
    op.drop_column("validation_runs", "footer_validation")
    op.drop_column("validation_runs", "mapping_format_checks")
    op.drop_column("validation_runs", "compared_columns")
    op.drop_column("validation_runs", "column_mappings")
    op.drop_column("validation_runs", "file_pair_key")
    op.drop_column("validation_runs", "target_path")
    op.drop_column("validation_runs", "source_path")
