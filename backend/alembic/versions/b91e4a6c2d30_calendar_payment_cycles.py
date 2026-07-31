"""separate calendar cycles from benefit payment dates

Revision ID: b91e4a6c2d30
Revises: f7c2a94e1b30
Create Date: 2026-07-31

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b91e4a6c2d30"
down_revision: str | Sequence[str] | None = "f7c2a94e1b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("payment_cycles", sa.Column("end_date", sa.Date(), nullable=True))
    op.execute(
        """
        UPDATE payment_cycles
        SET start_date = date(next_payment_date, 'start of month'),
            end_date = date(next_payment_date, 'start of month', '+1 month')
        """
    )
    with op.batch_alter_table("payment_cycles") as batch_op:
        batch_op.drop_constraint("ck_payment_cycles_date_order", type_="check")
        batch_op.alter_column("end_date", existing_type=sa.Date(), nullable=False)
        batch_op.create_check_constraint(
            "ck_payment_cycles_date_order",
            "end_date > start_date",
        )
        batch_op.create_check_constraint(
            "ck_payment_cycles_payment_within_cycle",
            "next_payment_date >= start_date AND next_payment_date < end_date",
        )
        batch_op.create_index("ix_payment_cycles_end_date", ["end_date"])
    op.execute(
        """
        UPDATE commitments
        SET payment_cycle_id = (
            SELECT payment_cycles.id
            FROM payment_cycles
            WHERE payment_cycles.currency = commitments.currency
              AND commitments.due_date >= payment_cycles.start_date
              AND commitments.due_date < payment_cycles.end_date
            ORDER BY payment_cycles.start_date DESC
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM payment_cycles
            WHERE payment_cycles.currency = commitments.currency
              AND commitments.due_date >= payment_cycles.start_date
              AND commitments.due_date < payment_cycles.end_date
        )
        """
    )
    op.execute(
        """
        UPDATE expenses
        SET payment_cycle_id = (
            SELECT payment_cycles.id
            FROM payment_cycles
            WHERE payment_cycles.currency = expenses.currency
              AND expenses.transaction_date >= payment_cycles.start_date
              AND expenses.transaction_date < payment_cycles.end_date
            ORDER BY payment_cycles.start_date DESC
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM payment_cycles
            WHERE payment_cycles.currency = expenses.currency
              AND expenses.transaction_date >= payment_cycles.start_date
              AND expenses.transaction_date < payment_cycles.end_date
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("payment_cycles") as batch_op:
        batch_op.drop_index("ix_payment_cycles_end_date")
        batch_op.drop_constraint(
            "ck_payment_cycles_payment_within_cycle",
            type_="check",
        )
        batch_op.drop_constraint("ck_payment_cycles_date_order", type_="check")
        batch_op.create_check_constraint(
            "ck_payment_cycles_date_order",
            "next_payment_date > start_date",
        )
        batch_op.drop_column("end_date")
