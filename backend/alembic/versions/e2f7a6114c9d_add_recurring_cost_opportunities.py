"""add recurring cost opportunities

Revision ID: e2f7a6114c9d
Revises: c8a4e72d91b0
Create Date: 2026-07-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e2f7a6114c9d"
down_revision: str | Sequence[str] | None = "c8a4e72d91b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_cost_opportunities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("current_monthly_cost", sa.Integer(), nullable=False),
        sa.Column("replacement_monthly_cost", sa.Integer(), nullable=True),
        sa.Column("one_off_switching_cost", sa.Integer(), server_default="0", nullable=False),
        sa.Column("difficulty", sa.String(length=8), server_default="moderate", nullable=False),
        sa.Column("decision", sa.String(length=8), server_default="review", nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
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
            "current_monthly_cost >= 0",
            name="ck_opportunity_current_nonnegative",
        ),
        sa.CheckConstraint(
            "replacement_monthly_cost IS NULL OR replacement_monthly_cost >= 0",
            name="ck_opportunity_replacement_nonnegative",
        ),
        sa.CheckConstraint(
            "one_off_switching_cost >= 0",
            name="ck_opportunity_switching_cost_nonnegative",
        ),
        sa.CheckConstraint("length(currency) = 3", name="ck_opportunity_currency_length"),
        sa.CheckConstraint(
            "difficulty IN ('easy', 'moderate', 'hard')",
            name="opportunity_difficulty",
        ),
        sa.CheckConstraint(
            "decision IN ('review', 'planned', 'accepted', 'rejected')",
            name="opportunity_decision",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "description",
            "currency",
            name="uq_opportunity_description_currency",
        ),
    )


def downgrade() -> None:
    op.drop_table("recurring_cost_opportunities")
