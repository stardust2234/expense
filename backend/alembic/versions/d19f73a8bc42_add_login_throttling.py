"""Add persistent login throttling.

Revision ID: d19f73a8bc42
Revises: c84a2d51e609
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d19f73a8bc42"
down_revision: str | None = "c84a2d51e609"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_throttles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint("key_hash", name="uq_login_throttles_key_hash"),
    )
    op.create_index("ix_login_throttles_key_hash", "login_throttles", ["key_hash"], unique=True)
    op.create_index("ix_login_throttles_blocked_until", "login_throttles", ["blocked_until"])


def downgrade() -> None:
    op.drop_index("ix_login_throttles_blocked_until", table_name="login_throttles")
    op.drop_index("ix_login_throttles_key_hash", table_name="login_throttles")
    op.drop_table("login_throttles")
