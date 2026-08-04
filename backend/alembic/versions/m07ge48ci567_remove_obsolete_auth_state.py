"""Rename action throttles and remove dormant user state.

Revision ID: m07ge48ci567
Revises: l96fd37bh456
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "m07ge48ci567"
down_revision: str | None = "l96fd37bh456"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("registration_throttles", "auth_action_throttles")
    op.drop_index("ix_registration_throttles_key_hash", table_name="auth_action_throttles")
    op.drop_index("ix_registration_throttles_blocked_until", table_name="auth_action_throttles")
    op.create_index(
        "ix_auth_action_throttles_key_hash",
        "auth_action_throttles",
        ["key_hash"],
        unique=True,
    )
    op.create_index(
        "ix_auth_action_throttles_blocked_until",
        "auth_action_throttles",
        ["blocked_until"],
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_active")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )
    op.drop_index("ix_auth_action_throttles_key_hash", table_name="auth_action_throttles")
    op.drop_index("ix_auth_action_throttles_blocked_until", table_name="auth_action_throttles")
    op.rename_table("auth_action_throttles", "registration_throttles")
    op.create_index(
        "ix_registration_throttles_key_hash",
        "registration_throttles",
        ["key_hash"],
        unique=True,
    )
    op.create_index(
        "ix_registration_throttles_blocked_until",
        "registration_throttles",
        ["blocked_until"],
    )
