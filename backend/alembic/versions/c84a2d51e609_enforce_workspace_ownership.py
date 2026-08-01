"""Enforce non-null workspace ownership.

Revision ID: c84a2d51e609
Revises: b73d9e1a4f20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c84a2d51e609"
down_revision: str | None = "b73d9e1a4f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNED_TABLES = (
    "categories",
    "categorisation_rules",
    "merchants",
    "merchant_aliases",
    "import_batches",
    "raw_transactions",
    "expenses",
    "payment_cycles",
    "commitments",
    "cycle_allowances",
    "recurring_cost_opportunities",
)


def upgrade() -> None:
    for table_name in OWNED_TABLES:
        missing = (
            op.get_bind()
            .execute(sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE workspace_id IS NULL"))
            .scalar_one()
        )
        if missing:
            raise RuntimeError(f"{table_name} contains {missing} records without a workspace")
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column("workspace_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    for table_name in reversed(OWNED_TABLES):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column("workspace_id", existing_type=sa.Integer(), nullable=True)
