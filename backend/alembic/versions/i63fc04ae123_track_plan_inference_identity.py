"""Track stable financial-plan inference identities.

Revision ID: i63fc04ae123
Revises: h52eb93fd012
"""

import sqlalchemy as sa

from alembic import op

revision = "i63fc04ae123"
down_revision = "h52eb93fd012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "commitments", sa.Column("inference_identity_key", sa.String(length=255), nullable=True)
    )
    op.create_index(
        "ix_commitments_inference_identity_key",
        "commitments",
        ["inference_identity_key"],
    )
    op.add_column(
        "cycle_allowances",
        sa.Column("inference_identity_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_cycle_allowances_inference_identity_key",
        "cycle_allowances",
        ["inference_identity_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_cycle_allowances_inference_identity_key", table_name="cycle_allowances")
    op.drop_column("cycle_allowances", "inference_identity_key")
    op.drop_index("ix_commitments_inference_identity_key", table_name="commitments")
    op.drop_column("commitments", "inference_identity_key")
