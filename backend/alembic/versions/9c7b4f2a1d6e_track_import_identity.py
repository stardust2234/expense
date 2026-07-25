"""track import identity

Revision ID: 9c7b4f2a1d6e
Revises: 558b529a85c3
Create Date: 2026-07-25 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9c7b4f2a1d6e"
down_revision: str | Sequence[str] | None = "558b529a85c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("content_sha256", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("default_currency", sa.String(length=3), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_import_batches_content_sha256"),
            ["content_sha256"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("import_batches", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_import_batches_content_sha256"))
        batch_op.drop_column("default_currency")
        batch_op.drop_column("content_sha256")
