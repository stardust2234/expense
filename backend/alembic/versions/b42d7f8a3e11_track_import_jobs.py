"""track import jobs

Revision ID: b42d7f8a3e11
Revises: 9c7b4f2a1d6e
Create Date: 2026-07-25 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b42d7f8a3e11"
down_revision: str | Sequence[str] | None = "9c7b4f2a1d6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "processing_status",
                sa.String(length=30),
                server_default="queued",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("processing_error", sa.String(length=1000), nullable=True))
        batch_op.add_column(
            sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("processing_completed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_import_batches_processing_status"),
            ["processing_status"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            UPDATE import_batches
            SET processing_status = CASE
                WHEN EXISTS (
                    SELECT 1
                    FROM raw_transactions
                    WHERE raw_transactions.import_batch_id = import_batches.id
                      AND raw_transactions.normalisation_error IS NOT NULL
                ) THEN 'completed_with_errors'
                ELSE 'completed'
            END,
            processing_completed_at = imported_at
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_import_batches_processing_status"))
        batch_op.drop_column("processing_completed_at")
        batch_op.drop_column("processing_started_at")
        batch_op.drop_column("processing_error")
        batch_op.drop_column("processing_status")
