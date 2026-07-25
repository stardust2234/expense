"""add safe spending plan

Revision ID: c8a4e72d91b0
Revises: b42d7f8a3e11
Create Date: 2026-07-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8a4e72d91b0"
down_revision: str | Sequence[str] | None = "b42d7f8a3e11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SPENDING_PRIORITIES = (
    "protected",
    "essential",
    "adjustable",
    "optional",
    "irregular_essential",
    "transfer",
)


def spending_priority_check(column_name: str) -> str:
    values = ", ".join(f"'{value}'" for value in SPENDING_PRIORITIES)
    return f"{column_name} IN ({values})"


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(
            sa.Column(
                "default_priority",
                sa.String(length=19),
                server_default="adjustable",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "category_spending_priority",
            spending_priority_check("default_priority"),
        )

    op.create_table(
        "payment_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("next_payment_date", sa.Date(), nullable=False),
        sa.Column("expected_income_amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("opening_balance", sa.Integer(), nullable=False),
        sa.Column("current_balance", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=7), server_default="planned", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'closed')",
            name="payment_cycle_status",
        ),
        sa.CheckConstraint(
            "next_payment_date > start_date",
            name="ck_payment_cycles_date_order",
        ),
        sa.CheckConstraint(
            "expected_income_amount >= 0",
            name="ck_payment_cycles_expected_income_nonnegative",
        ),
        sa.CheckConstraint(
            "length(currency) = 3",
            name="ck_payment_cycles_currency_length",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_cycles_start_date", "payment_cycles", ["start_date"])
    op.create_index(
        "ix_payment_cycles_next_payment_date",
        "payment_cycles",
        ["next_payment_date"],
    )
    op.create_index("ix_payment_cycles_status", "payment_cycles", ["status"])

    with op.batch_alter_table("expenses") as batch_op:
        batch_op.add_column(sa.Column("payment_cycle_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("priority_override", sa.String(length=19), nullable=True))
        batch_op.create_foreign_key(
            "fk_expenses_payment_cycle_id",
            "payment_cycles",
            ["payment_cycle_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "expense_spending_priority",
            f"priority_override IS NULL OR {spending_priority_check('priority_override')}",
        )
        batch_op.create_index("ix_expenses_payment_cycle_id", ["payment_cycle_id"])

    op.create_table(
        "commitments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_cycle_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("priority", sa.String(length=19), server_default="protected", nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=7), server_default="pending", nullable=False),
        sa.Column("recurrence", sa.String(length=50), nullable=True),
        sa.Column("matched_expense_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.CheckConstraint(
            spending_priority_check("priority"),
            name="commitment_spending_priority",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'paid', 'skipped')",
            name="commitment_status",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_commitments_amount_nonnegative"),
        sa.CheckConstraint("length(currency) = 3", name="ck_commitments_currency_length"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_expense_id"], ["expenses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["payment_cycle_id"],
            ["payment_cycles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("matched_expense_id"),
    )
    op.create_index("ix_commitments_payment_cycle_id", "commitments", ["payment_cycle_id"])
    op.create_index("ix_commitments_category_id", "commitments", ["category_id"])
    op.create_index("ix_commitments_due_date", "commitments", ["due_date"])
    op.create_index("ix_commitments_status", "commitments", ["status"])

    op.create_table(
        "cycle_allowances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_cycle_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("allowance_type", sa.String(length=14), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(length=19), server_default="essential", nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "allowance_type IN ('food', 'transport', 'irregular_cost', 'emergency', 'custom')",
            name="allowance_type",
        ),
        sa.CheckConstraint(
            spending_priority_check("priority"),
            name="allowance_spending_priority",
        ),
        sa.CheckConstraint("amount >= 0", name="ck_cycle_allowances_amount_nonnegative"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["payment_cycle_id"],
            ["payment_cycles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payment_cycle_id",
            "allowance_type",
            "category_id",
            name="uq_cycle_allowance_type_category",
        ),
    )
    op.create_index(
        "ix_cycle_allowances_payment_cycle_id",
        "cycle_allowances",
        ["payment_cycle_id"],
    )
    op.create_index("ix_cycle_allowances_category_id", "cycle_allowances", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_cycle_allowances_category_id", table_name="cycle_allowances")
    op.drop_index("ix_cycle_allowances_payment_cycle_id", table_name="cycle_allowances")
    op.drop_table("cycle_allowances")

    op.drop_index("ix_commitments_status", table_name="commitments")
    op.drop_index("ix_commitments_due_date", table_name="commitments")
    op.drop_index("ix_commitments_category_id", table_name="commitments")
    op.drop_index("ix_commitments_payment_cycle_id", table_name="commitments")
    op.drop_table("commitments")

    with op.batch_alter_table("expenses") as batch_op:
        batch_op.drop_index("ix_expenses_payment_cycle_id")
        batch_op.drop_constraint("expense_spending_priority", type_="check")
        batch_op.drop_constraint("fk_expenses_payment_cycle_id", type_="foreignkey")
        batch_op.drop_column("priority_override")
        batch_op.drop_column("payment_cycle_id")

    op.drop_index("ix_payment_cycles_status", table_name="payment_cycles")
    op.drop_index("ix_payment_cycles_next_payment_date", table_name="payment_cycles")
    op.drop_index("ix_payment_cycles_start_date", table_name="payment_cycles")
    op.drop_table("payment_cycles")

    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_constraint("category_spending_priority", type_="check")
        batch_op.drop_column("default_priority")
