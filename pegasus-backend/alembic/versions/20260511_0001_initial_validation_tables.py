# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-08T10:46:43Z
# --- END GENERATED FILE METADATA ---

"""Initial validation_runs and mismatch_reports tables.

Revision ID: 20260511_0001
Revises:
Create Date: 2026-05-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260511_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "validation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                name="validationrunstatus",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("source_filename", sa.String(length=512), nullable=True),
        sa.Column("target_filename", sa.String(length=512), nullable=True),
        sa.Column("uid_column", sa.String(length=256), nullable=False),
        sa.Column("delimiter", sa.String(length=8), nullable=False),
        sa.Column("missing_in_target_count", sa.Integer(), nullable=False),
        sa.Column("extra_in_target_count", sa.Integer(), nullable=False),
        sa.Column("value_mismatch_count", sa.Integer(), nullable=False),
        sa.Column("total_mismatch_records", sa.Integer(), nullable=False),
        sa.Column("source_row_count", sa.Integer(), nullable=True),
        sa.Column("target_row_count", sa.Integer(), nullable=True),
        sa.Column("compared_column_count", sa.Integer(), nullable=True),
        sa.Column("is_match", sa.Boolean(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mismatch_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("validation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uid", sa.String(length=1024), nullable=False),
        sa.Column("mismatch_type", sa.String(length=64), nullable=False),
        sa.Column("column_name", sa.String(length=512), nullable=True),
        sa.Column("source_value", sa.Text(), nullable=True),
        sa.Column("target_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["validation_run_id"], ["validation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mismatch_reports_validation_run_id",
        "mismatch_reports",
        ["validation_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mismatch_reports_validation_run_id", table_name="mismatch_reports")
    op.drop_table("mismatch_reports")
    op.drop_table("validation_runs")
