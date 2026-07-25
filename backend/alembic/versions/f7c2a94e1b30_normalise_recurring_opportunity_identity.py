"""normalise recurring opportunity identity

Revision ID: f7c2a94e1b30
Revises: a6d3c91f20b7
Create Date: 2026-07-25

"""

from collections.abc import Sequence
from unicodedata import normalize

import sqlalchemy as sa

from alembic import op

revision: str = "f7c2a94e1b30"
down_revision: str | Sequence[str] | None = "a6d3c91f20b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _description_key(value: str) -> str:
    return f"description:{' '.join(normalize('NFKC', value).casefold().split())}"


def upgrade() -> None:
    op.add_column(
        "recurring_cost_opportunities",
        sa.Column("identity_key", sa.String(length=600), nullable=True),
    )

    connection = op.get_bind()
    merchant_ids = {
        " ".join(normalize("NFKC", name).casefold().split()): merchant_id
        for merchant_id, name in connection.execute(sa.text("SELECT id, name FROM merchants"))
    }
    rows = connection.execute(
        sa.text(
            "SELECT id, description, currency FROM recurring_cost_opportunities "
            "ORDER BY updated_at DESC, id DESC"
        )
    ).all()
    seen: set[tuple[str, str]] = set()
    for opportunity_id, description, currency in rows:
        description_identity = " ".join(normalize("NFKC", description).casefold().split())
        merchant_id = merchant_ids.get(description_identity)
        identity_key = (
            f"merchant:{merchant_id}" if merchant_id is not None else _description_key(description)
        )
        identity = (identity_key, currency)
        if identity in seen:
            connection.execute(
                sa.text("DELETE FROM recurring_cost_opportunities WHERE id = :id"),
                {"id": opportunity_id},
            )
            continue
        seen.add(identity)
        connection.execute(
            sa.text(
                "UPDATE recurring_cost_opportunities "
                "SET identity_key = :identity_key WHERE id = :id"
            ),
            {"identity_key": identity_key, "id": opportunity_id},
        )

    with op.batch_alter_table("recurring_cost_opportunities") as batch_op:
        batch_op.drop_constraint("uq_opportunity_description_currency", type_="unique")
        batch_op.alter_column("identity_key", existing_type=sa.String(length=600), nullable=False)
        batch_op.create_unique_constraint(
            "uq_opportunity_identity_currency",
            ["identity_key", "currency"],
        )


def downgrade() -> None:
    with op.batch_alter_table("recurring_cost_opportunities") as batch_op:
        batch_op.drop_constraint("uq_opportunity_identity_currency", type_="unique")
        batch_op.drop_column("identity_key")
        batch_op.create_unique_constraint(
            "uq_opportunity_description_currency",
            ["description", "currency"],
        )
