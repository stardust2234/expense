"""add import job lease

Revision ID: e63b814cf729
Revises: d52a71c9e604
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e63b814cf729"
down_revision: str | None = "d52a71c9e604"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("processing_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_import_batches_processing_lease_expires_at"),
        "import_batches",
        ["processing_lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_import_batches_processing_lease_expires_at"),
        table_name="import_batches",
    )
    op.drop_column("import_batches", "processing_lease_expires_at")
