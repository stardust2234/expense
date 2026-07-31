"""track duplicate import rows

Revision ID: c34f1d8a72e5
Revises: b91e4a6c2d30
Create Date: 2026-07-31

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c34f1d8a72e5"
down_revision: str | Sequence[str] | None = "b91e4a6c2d30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("raw_transactions") as batch_op:
        batch_op.add_column(sa.Column("duplicate_of_expense_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_raw_transactions_duplicate_of_expense_id",
            "expenses",
            ["duplicate_of_expense_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_raw_transactions_duplicate_of_expense_id",
            ["duplicate_of_expense_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("raw_transactions") as batch_op:
        batch_op.drop_index("ix_raw_transactions_duplicate_of_expense_id")
        batch_op.drop_constraint(
            "fk_raw_transactions_duplicate_of_expense_id",
            type_="foreignkey",
        )
        batch_op.drop_column("duplicate_of_expense_id")
