# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-24T04:59:03Z
# --- END GENERATED FILE METADATA ---

"""Backfill value_mismatch_row_count from persisted mismatch rows.

Revision ID: 20260623_0010
Revises: 20260623_0009
Create Date: 2026-06-23
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260623_0010"
down_revision: Union[str, Sequence[str], None] = "20260623_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE validation_runs AS vr
            SET value_mismatch_row_count = sub.row_count
            FROM (
                SELECT
                    validation_run_id,
                    COUNT(DISTINCT uid) AS row_count
                FROM mismatch_reports
                WHERE mismatch_type = 'value_mismatch'
                GROUP BY validation_run_id
            ) AS sub
            WHERE vr.id = sub.validation_run_id
              AND sub.row_count > 0
            """
        )
    )


def downgrade() -> None:
    pass
