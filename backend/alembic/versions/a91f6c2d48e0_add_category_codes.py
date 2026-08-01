"""Add stable codes for seeded categories.

Revision ID: a91f6c2d48e0
Revises: e63b814cf729
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a91f6c2d48e0"
down_revision: str | None = "e63b814cf729"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORY_TAXONOMY = (
    ("Housing", ("Rent", "Council tax", "Repairs")),
    ("Utilities", ("Electricity", "Water", "Internet", "Mobile")),
    ("Groceries", ("Supermarkets", "Food shops")),
    ("Transport", ("Public transport", "Fuel", "Taxi", "Maintenance")),
    ("Eating out", ("Restaurants", "Takeaway", "Cafés")),
    ("Shopping", ("Clothing", "Electronics", "Household items")),
    ("Health", ("Pharmacy", "Dentist", "Healthcare")),
    ("Personal care", ("Toiletries", "Haircare", "Beauty")),
    ("Entertainment", ("Streaming", "Games", "Events")),
    ("Financial", ("Bank fees", "Loan interest", "Insurance")),
    ("Subscriptions", ("Software", "Memberships")),
    ("Savings and investments", ("ISA", "SIPP", "Savings")),
    ("Income", ("Salary", "Refunds", "Benefits")),
    ("Transfers", ("Own-account transfers", "Credit-card payments")),
    ("Other", ("Uncategorized", "Exceptional expenses")),
)


def _slug(value: str) -> str:
    return "_".join(value.casefold().replace("-", " ").split())


def upgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.add_column(sa.Column("code", sa.String(length=100), nullable=True))
        batch_op.create_index("ix_categories_code", ["code"], unique=True)

    connection = op.get_bind()
    for parent_name, children in CATEGORY_TAXONOMY:
        parent_code = _slug(parent_name)
        connection.execute(
            sa.text("UPDATE categories SET code = :code WHERE name = :name AND code IS NULL"),
            {"code": parent_code, "name": parent_name},
        )
        for child_name in children:
            connection.execute(
                sa.text("UPDATE categories SET code = :code WHERE name = :name AND code IS NULL"),
                {"code": f"{parent_code}.{_slug(child_name)}", "name": child_name},
            )


def downgrade() -> None:
    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_index("ix_categories_code")
        batch_op.drop_column("code")
