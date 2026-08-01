"""Add pending user email for verified address changes.

Revision ID: h52eb93fd012
Revises: g41da82ec901
"""

import sqlalchemy as sa

from alembic import op

revision = "h52eb93fd012"
down_revision = "g41da82ec901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_email", sa.String(length=320), nullable=True))
    op.create_index("ix_users_pending_email", "users", ["pending_email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_pending_email", table_name="users")
    op.drop_column("users", "pending_email")
