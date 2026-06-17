# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-17T06:57:27Z
# --- END GENERATED FILE METADATA ---

"""Encrypt persisted validation history payloads.

Revision ID: 20260521_0004
Revises: 20260518_0003
Create Date: 2026-05-21

"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from pegasus.core.field_encryption import decrypt_value, encrypt_value

revision: str = "20260521_0004"
down_revision: Union[str, Sequence[str], None] = "20260518_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _jsonb_token(value: object) -> str:
    return json.dumps(encrypt_value(value))


def _restore_jsonb_value(value: object) -> object:
    decrypted = decrypt_value(value)
    if isinstance(decrypted, str):
        return json.loads(decrypted)
    return decrypted


def upgrade() -> None:
    op.alter_column("validation_runs", "column_mappings", server_default=None)
    op.alter_column(
        "validation_runs",
        "delimiter",
        existing_type=sa.String(length=8),
        type_=sa.Text(),
    )
    op.alter_column(
        "mismatch_reports",
        "mismatch_type",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
    )

    conn = op.get_bind()

    run_rows = conn.execute(
        sa.text(
            """
            SELECT id, source_filename, target_filename, source_path, target_path, uid_column, delimiter,
                   column_mappings, compared_columns, mapping_format_checks, footer_validation, error_detail
            FROM validation_runs
            """
        )
    ).mappings()
    for row in run_rows:
        conn.execute(
            sa.text(
                """
                UPDATE validation_runs
                SET source_filename = :source_filename,
                    target_filename = :target_filename,
                    source_path = :source_path,
                    target_path = :target_path,
                    uid_column = :uid_column,
                    delimiter = :delimiter,
                    column_mappings = CAST(:column_mappings AS JSONB),
                    compared_columns = CAST(:compared_columns AS JSONB),
                    mapping_format_checks = CAST(:mapping_format_checks AS JSONB),
                    footer_validation = CAST(:footer_validation AS JSONB),
                    error_detail = :error_detail
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "source_filename": encrypt_value(row["source_filename"]) if row["source_filename"] is not None else None,
                "target_filename": encrypt_value(row["target_filename"]) if row["target_filename"] is not None else None,
                "source_path": encrypt_value(row["source_path"]) if row["source_path"] is not None else None,
                "target_path": encrypt_value(row["target_path"]) if row["target_path"] is not None else None,
                "uid_column": encrypt_value(row["uid_column"]),
                "delimiter": encrypt_value(row["delimiter"]),
                "column_mappings": _jsonb_token(row["column_mappings"]),
                "compared_columns": _jsonb_token(row["compared_columns"]) if row["compared_columns"] is not None else None,
                "mapping_format_checks": _jsonb_token(row["mapping_format_checks"]) if row["mapping_format_checks"] is not None else None,
                "footer_validation": _jsonb_token(row["footer_validation"]) if row["footer_validation"] is not None else None,
                "error_detail": encrypt_value(row["error_detail"]) if row["error_detail"] is not None else None,
            },
        )

    mismatch_rows = conn.execute(
        sa.text(
            """
            SELECT id, uid, mismatch_type, column_name, source_value, target_value, row_detail
            FROM mismatch_reports
            """
        )
    ).mappings()
    for row in mismatch_rows:
        conn.execute(
            sa.text(
                """
                UPDATE mismatch_reports
                SET uid = :uid,
                    mismatch_type = :mismatch_type,
                    column_name = :column_name,
                    source_value = :source_value,
                    target_value = :target_value,
                    row_detail = :row_detail
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "uid": encrypt_value(row["uid"]),
                "mismatch_type": encrypt_value(row["mismatch_type"]),
                "column_name": encrypt_value(row["column_name"]) if row["column_name"] is not None else None,
                "source_value": encrypt_value(row["source_value"]) if row["source_value"] is not None else None,
                "target_value": encrypt_value(row["target_value"]) if row["target_value"] is not None else None,
                "row_detail": encrypt_value(row["row_detail"]) if row["row_detail"] is not None else None,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    run_rows = conn.execute(
        sa.text(
            """
            SELECT id, source_filename, target_filename, source_path, target_path, uid_column, delimiter,
                   column_mappings, compared_columns, mapping_format_checks, footer_validation, error_detail
            FROM validation_runs
            """
        )
    ).mappings()
    for row in run_rows:
        conn.execute(
            sa.text(
                """
                UPDATE validation_runs
                SET source_filename = :source_filename,
                    target_filename = :target_filename,
                    source_path = :source_path,
                    target_path = :target_path,
                    uid_column = :uid_column,
                    delimiter = :delimiter,
                    column_mappings = CAST(:column_mappings AS JSONB),
                    compared_columns = CAST(:compared_columns AS JSONB),
                    mapping_format_checks = CAST(:mapping_format_checks AS JSONB),
                    footer_validation = CAST(:footer_validation AS JSONB),
                    error_detail = :error_detail
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "source_filename": decrypt_value(row["source_filename"]),
                "target_filename": decrypt_value(row["target_filename"]),
                "source_path": decrypt_value(row["source_path"]),
                "target_path": decrypt_value(row["target_path"]),
                "uid_column": decrypt_value(row["uid_column"]),
                "delimiter": decrypt_value(row["delimiter"]),
                "column_mappings": json.dumps(_restore_jsonb_value(row["column_mappings"])),
                "compared_columns": json.dumps(_restore_jsonb_value(row["compared_columns"])) if row["compared_columns"] is not None else None,
                "mapping_format_checks": json.dumps(_restore_jsonb_value(row["mapping_format_checks"])) if row["mapping_format_checks"] is not None else None,
                "footer_validation": json.dumps(_restore_jsonb_value(row["footer_validation"])) if row["footer_validation"] is not None else None,
                "error_detail": decrypt_value(row["error_detail"]),
            },
        )

    mismatch_rows = conn.execute(
        sa.text(
            """
            SELECT id, uid, mismatch_type, column_name, source_value, target_value, row_detail
            FROM mismatch_reports
            """
        )
    ).mappings()
    for row in mismatch_rows:
        conn.execute(
            sa.text(
                """
                UPDATE mismatch_reports
                SET uid = :uid,
                    mismatch_type = :mismatch_type,
                    column_name = :column_name,
                    source_value = :source_value,
                    target_value = :target_value,
                    row_detail = :row_detail
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "uid": decrypt_value(row["uid"]),
                "mismatch_type": decrypt_value(row["mismatch_type"]),
                "column_name": decrypt_value(row["column_name"]),
                "source_value": decrypt_value(row["source_value"]),
                "target_value": decrypt_value(row["target_value"]),
                "row_detail": decrypt_value(row["row_detail"]),
            },
        )

    op.alter_column("validation_runs", "column_mappings", server_default=sa.text("'[]'::jsonb"))
    op.alter_column(
        "mismatch_reports",
        "mismatch_type",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
    )
    op.alter_column(
        "validation_runs",
        "delimiter",
        existing_type=sa.Text(),
        type_=sa.String(length=8),
    )
