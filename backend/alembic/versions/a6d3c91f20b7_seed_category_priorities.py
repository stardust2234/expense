"""seed category priorities

Revision ID: a6d3c91f20b7
Revises: e2f7a6114c9d
Create Date: 2026-07-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a6d3c91f20b7"
down_revision: str | Sequence[str] | None = "e2f7a6114c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRIORITY_NAMES: dict[str, tuple[str, ...]] = {
    "protected": (
        "Housing",
        "Rent",
        "Council tax",
        "Electricity",
        "Water",
        "Loan interest",
    ),
    "essential": (
        "Groceries",
        "Supermarkets",
        "Food shops",
        "Transport",
        "Public transport",
        "Fuel",
        "Health",
        "Pharmacy",
        "Healthcare",
        "Toiletries",
    ),
    "adjustable": (
        "Utilities",
        "Internet",
        "Mobile",
        "Taxi",
        "Shopping",
        "Personal care",
        "Haircare",
        "Financial",
        "Bank fees",
        "Insurance",
        "Other",
        "Uncategorized",
        "Exceptional expenses",
    ),
    "optional": (
        "Eating out",
        "Restaurants",
        "Takeaway",
        "Cafés",
        "Electronics",
        "Beauty",
        "Entertainment",
        "Streaming",
        "Games",
        "Events",
        "Subscriptions",
        "Software",
        "Memberships",
    ),
    "irregular_essential": (
        "Repairs",
        "Maintenance",
        "Clothing",
        "Household items",
        "Dentist",
    ),
    "transfer": (
        "Savings and investments",
        "ISA",
        "SIPP",
        "Savings",
        "Income",
        "Salary",
        "Refunds",
        "Benefits",
        "Transfers",
        "Own-account transfers",
        "Credit-card payments",
    ),
}


def upgrade() -> None:
    categories = sa.table(
        "categories",
        sa.column("name", sa.String()),
        sa.column("default_priority", sa.String()),
    )
    for priority, names in PRIORITY_NAMES.items():
        op.execute(
            categories.update()
            .where(categories.c.name.in_(names))
            .values(default_priority=priority)
        )


def downgrade() -> None:
    categories = sa.table(
        "categories",
        sa.column("name", sa.String()),
        sa.column("default_priority", sa.String()),
    )
    all_names = tuple(name for names in PRIORITY_NAMES.values() for name in names)
    op.execute(
        categories.update()
        .where(categories.c.name.in_(all_names))
        .values(default_priority="adjustable")
    )
