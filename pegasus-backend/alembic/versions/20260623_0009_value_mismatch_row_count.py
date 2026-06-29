# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-29T05:26:25Z
# --- END GENERATED FILE METADATA ---

"""Add value_mismatch_row_count to validation_runs.

Revision ID: 20260623_0009
Revises: 20260609_0008
Create Date: 2026-06-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0009"
down_revision: Union[str, Sequence[str], None] = "20260609_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "validation_runs",
        sa.Column("value_mismatch_row_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        sa.text(
            """
            UPDATE validation_runs
            SET value_mismatch_row_count = value_mismatch_count
            WHERE value_mismatch_count > 0
            """
        )
    )
    op.alter_column("validation_runs", "value_mismatch_row_count", server_default=None)


def downgrade() -> None:
    op.drop_column("validation_runs", "value_mismatch_row_count")
