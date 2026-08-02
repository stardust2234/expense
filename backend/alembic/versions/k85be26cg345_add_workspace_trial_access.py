"""Add workspace trial and paid-access expiry.

Revision ID: k85be26cg345
Revises: j74ad15bf234
"""

import sqlalchemy as sa

from alembic import op

revision = "k85be26cg345"
down_revision = "j74ad15bf234"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.add_column(sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_workspaces_access_expires_at", ["access_expires_at"])
    op.execute("UPDATE workspaces SET trial_ends_at = datetime('now', '+30 days')")
    with op.batch_alter_table("workspaces") as batch:
        batch.alter_column(
            "trial_ends_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("workspaces") as batch:
        batch.drop_index("ix_workspaces_access_expires_at")
        batch.drop_column("access_expires_at")
        batch.drop_column("trial_ends_at")
