"""Add account security tokens, throttles, and audit log.

Revision ID: g41da82ec901
Revises: f38bc519d204
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g41da82ec901"
down_revision: str | None = "f38bc519d204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_hash"),
    )
    for column in ("user_id", "purpose", "token_hash", "expires_at"):
        op.create_index(
            f"ix_account_tokens_{column}", "account_tokens", [column], unique=column == "token_hash"
        )
    op.create_table(
        "registration_throttles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index(
        "ix_registration_throttles_key_hash", "registration_throttles", ["key_hash"], unique=True
    )
    op.create_index(
        "ix_registration_throttles_blocked_until", "registration_throttles", ["blocked_until"]
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id", ondelete="SET NULL")
        ),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("client_ip", sa.String(64)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    for column in ("workspace_id", "actor_user_id", "target_user_id", "event_type", "created_at"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("registration_throttles")
    op.drop_table("account_tokens")
