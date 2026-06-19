# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T07:02:42Z
# --- END GENERATED FILE METADATA ---

"""Add server_default values to mismatch count columns.

Revision ID: 20260609_0008
Revises: 20260602_0007
Create Date: 2026-06-09
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260609_0008"
down_revision: Union[str, Sequence[str], None] = "20260602_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, update any existing NULL values to 0 (if any exist despite nullable=False)
    op.execute(
        sa.text(
            """
            UPDATE validation_runs
            SET missing_in_target_count = 0
            WHERE missing_in_target_count IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE validation_runs
            SET extra_in_target_count = 0
            WHERE extra_in_target_count IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE validation_runs
            SET value_mismatch_count = 0
            WHERE value_mismatch_count IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE validation_runs
            SET total_mismatch_records = 0
            WHERE total_mismatch_records IS NULL
            """
        )
    )

    # Add server_default values
    op.alter_column(
        "validation_runs",
        "missing_in_target_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
    op.alter_column(
        "validation_runs",
        "extra_in_target_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
    op.alter_column(
        "validation_runs",
        "value_mismatch_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
    op.alter_column(
        "validation_runs",
        "total_mismatch_records",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )


def downgrade() -> None:
    # Remove server_default values
    op.alter_column(
        "validation_runs",
        "total_mismatch_records",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        "validation_runs",
        "value_mismatch_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        "validation_runs",
        "extra_in_target_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        "validation_runs",
        "missing_in_target_count",
        existing_type=sa.Integer(),
        nullable=False,
        server_default=None,
    )
