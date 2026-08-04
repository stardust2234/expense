"""Replace workspace memberships with direct ownership.

Revision ID: l96fd37bh456
Revises: k85be26cg345
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "l96fd37bh456"
down_revision: str | None = "k85be26cg345"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    duplicate_workspace_owners = connection.execute(
        sa.text(
            "SELECT workspace_id FROM workspace_memberships "
            "WHERE role = 'owner' GROUP BY workspace_id HAVING COUNT(*) > 1"
        )
    ).first()
    if duplicate_workspace_owners is not None:
        raise RuntimeError("A workspace has more than one owner")

    duplicate_user_ownership = connection.execute(
        sa.text(
            "SELECT user_id FROM workspace_memberships "
            "WHERE role = 'owner' GROUP BY user_id HAVING COUNT(*) > 1"
        )
    ).first()
    if duplicate_user_ownership is not None:
        raise RuntimeError("A user owns more than one workspace")

    claimed_without_owner = connection.execute(
        sa.text(
            "SELECT w.id FROM workspaces AS w "
            "LEFT JOIN workspace_memberships AS m "
            "ON m.workspace_id = w.id AND m.role = 'owner' "
            "WHERE w.is_claimed = 1 AND m.id IS NULL LIMIT 1"
        )
    ).first()
    if claimed_without_owner is not None:
        raise RuntimeError("A claimed workspace has no owner")

    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_workspaces_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    connection.execute(
        sa.text(
            "UPDATE workspaces SET owner_user_id = ("
            "SELECT user_id FROM workspace_memberships "
            "WHERE workspace_memberships.workspace_id = workspaces.id "
            "AND role = 'owner' LIMIT 1)"
        )
    )
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"], unique=True)
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.create_check_constraint(
            "ck_workspaces_claimed_owner",
            "(is_claimed = 0 AND owner_user_id IS NULL) OR "
            "(is_claimed = 1 AND owner_user_id IS NOT NULL)",
        )
    op.drop_table("workspace_memberships")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_admin")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.Integer(),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),
    )
    op.create_index(
        "ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"]
    )
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO workspace_memberships (workspace_id, user_id, role) "
            "SELECT id, owner_user_id, 'owner' FROM workspaces WHERE owner_user_id IS NOT NULL"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE users SET is_admin = 1 WHERE id IN ("
            "SELECT owner_user_id FROM workspaces WHERE owner_user_id IS NOT NULL)"
        )
    )
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    with op.batch_alter_table("workspaces") as batch_op:
        batch_op.drop_constraint("ck_workspaces_claimed_owner", type_="check")
        batch_op.drop_constraint("fk_workspaces_owner_user_id_users", type_="foreignkey")
        batch_op.drop_column("owner_user_id")
