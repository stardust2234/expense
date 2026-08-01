"""Scope financial uniqueness to each workspace.

Revision ID: e27a410bc835
Revises: d19f73a8bc42
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e27a410bc835"
down_revision: str | None = "d19f73a8bc42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAMING_CONVENTION = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    with op.batch_alter_table("categories", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("uq_categories_name", type_="unique")
        batch_op.drop_index("ix_categories_code")
        batch_op.create_index("ix_categories_code", ["code"], unique=False)
        batch_op.create_unique_constraint("uq_categories_workspace_code", ["workspace_id", "code"])
        batch_op.create_unique_constraint("uq_categories_workspace_name", ["workspace_id", "name"])
    with op.batch_alter_table("merchants", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("uq_merchants_name", type_="unique")
        batch_op.create_unique_constraint("uq_merchants_workspace_name", ["workspace_id", "name"])
    with op.batch_alter_table("merchant_aliases", naming_convention=NAMING_CONVENTION) as batch_op:
        batch_op.drop_constraint("uq_merchant_aliases_pattern", type_="unique")
        batch_op.create_unique_constraint(
            "uq_aliases_workspace_pattern", ["workspace_id", "pattern"]
        )
    with op.batch_alter_table("recurring_cost_opportunities") as batch_op:
        batch_op.drop_constraint("uq_opportunity_identity_currency", type_="unique")
        batch_op.create_unique_constraint(
            "uq_opportunity_workspace_identity_currency",
            ["workspace_id", "identity_key", "currency"],
        )


def downgrade() -> None:
    with op.batch_alter_table("recurring_cost_opportunities") as batch_op:
        batch_op.drop_constraint("uq_opportunity_workspace_identity_currency", type_="unique")
        batch_op.create_unique_constraint(
            "uq_opportunity_identity_currency", ["identity_key", "currency"]
        )
    with op.batch_alter_table("merchant_aliases") as batch_op:
        batch_op.drop_constraint("uq_aliases_workspace_pattern", type_="unique")
        batch_op.create_unique_constraint("uq_merchant_aliases_pattern", ["pattern"])
    with op.batch_alter_table("merchants") as batch_op:
        batch_op.drop_constraint("uq_merchants_workspace_name", type_="unique")
        batch_op.create_unique_constraint("uq_merchants_name", ["name"])
    with op.batch_alter_table("categories") as batch_op:
        batch_op.drop_constraint("uq_categories_workspace_name", type_="unique")
        batch_op.drop_constraint("uq_categories_workspace_code", type_="unique")
        batch_op.drop_index("ix_categories_code")
        batch_op.create_index("ix_categories_code", ["code"], unique=True)
        batch_op.create_unique_constraint("uq_categories_name", ["name"])
