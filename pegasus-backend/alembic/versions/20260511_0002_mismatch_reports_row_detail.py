# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T07:01:32Z
# --- END GENERATED FILE METADATA ---

"""Add row_detail JSON column to mismatch_reports.

Revision ID: 20260511_0002
Revises: 20260511_0001
Create Date: 2026-05-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0002"
down_revision: Union[str, Sequence[str], None] = "20260511_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mismatch_reports", sa.Column("row_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("mismatch_reports", "row_detail")
