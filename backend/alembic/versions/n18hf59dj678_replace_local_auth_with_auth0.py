"""Replace local credentials and sessions with Auth0 identity mapping.

Revision ID: n18hf59dj678
Revises: m07ge48ci567
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "n18hf59dj678"
down_revision: str | None = "m07ge48ci567"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name in (
        "audit_events",
        "account_tokens",
        "auth_sessions",
        "login_throttles",
        "auth_action_throttles",
    ):
        op.drop_table(table_name)
    op.drop_index("ix_users_pending_email", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("auth0_subject", sa.String(length=255), nullable=True))
        batch_op.drop_column("pending_email")
        batch_op.drop_column("email_verified_at")
        batch_op.drop_column("password_hash")
    op.create_index("ix_users_auth0_subject", "users", ["auth0_subject"], unique=True)


def downgrade() -> None:
    raise RuntimeError("Downgrading from Auth0 to local credentials is not supported")
