"""add import job claim token

Revision ID: d52a71c9e604
Revises: c34f1d8a72e5
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d52a71c9e604"
down_revision: str | None = "c34f1d8a72e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "import_batches",
        sa.Column("processing_claim_token", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_import_batches_processing_claim_token"),
        "import_batches",
        ["processing_claim_token"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_import_batches_processing_claim_token"), table_name="import_batches")
    op.drop_column("import_batches", "processing_claim_token")
