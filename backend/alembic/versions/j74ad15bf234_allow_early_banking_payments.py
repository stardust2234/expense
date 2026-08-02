"""Allow an income date adjusted before the calendar month.

Revision ID: j74ad15bf234
Revises: i63fc04ae123
"""

from alembic import op

revision = "j74ad15bf234"
down_revision = "i63fc04ae123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("payment_cycles") as batch:
        batch.drop_constraint("ck_payment_cycles_payment_within_cycle", type_="check")
        batch.create_check_constraint(
            "ck_payment_cycles_payment_within_cycle",
            "next_payment_date >= date(start_date, '-7 days') AND next_payment_date < end_date",
        )


def downgrade() -> None:
    with op.batch_alter_table("payment_cycles") as batch:
        batch.drop_constraint("ck_payment_cycles_payment_within_cycle", type_="check")
        batch.create_check_constraint(
            "ck_payment_cycles_payment_within_cycle",
            "next_payment_date >= start_date AND next_payment_date < end_date",
        )
