"""Remove auth constraints duplicated by unique indexes.

Revision ID: f38bc519d204
Revises: e27a410bc835
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f38bc519d204"
down_revision: str | None = "e27a410bc835"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table_name, constraint_name in (
        ("users", "uq_users_email"),
        ("auth_sessions", "uq_auth_sessions_token_hash"),
        ("login_throttles", "uq_login_throttles_key_hash"),
    ):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="unique")


def downgrade() -> None:
    for table_name, constraint_name, column_name in (
        ("users", "uq_users_email", "email"),
        ("auth_sessions", "uq_auth_sessions_token_hash", "token_hash"),
        ("login_throttles", "uq_login_throttles_key_hash", "key_hash"),
    ):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_unique_constraint(constraint_name, [column_name])
