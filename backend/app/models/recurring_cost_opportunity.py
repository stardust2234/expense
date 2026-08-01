from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.workspace_owned import WorkspaceOwned


class OpportunityDifficulty(str, Enum):
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"


class OpportunityDecision(str, Enum):
    REVIEW = "review"
    PLANNED = "planned"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RecurringCostOpportunity(WorkspaceOwned, Base):
    __tablename__ = "recurring_cost_opportunities"
    __table_args__ = (
        CheckConstraint("current_monthly_cost >= 0", name="ck_opportunity_current_nonnegative"),
        CheckConstraint(
            "replacement_monthly_cost IS NULL OR replacement_monthly_cost >= 0",
            name="ck_opportunity_replacement_nonnegative",
        ),
        CheckConstraint(
            "one_off_switching_cost >= 0",
            name="ck_opportunity_switching_cost_nonnegative",
        ),
        CheckConstraint("length(currency) = 3", name="ck_opportunity_currency_length"),
        UniqueConstraint(
            "workspace_id",
            "identity_key",
            "currency",
            name="uq_opportunity_workspace_identity_currency",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    identity_key: Mapped[str] = mapped_column(String(600), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    current_monthly_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    replacement_monthly_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    one_off_switching_cost: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    difficulty: Mapped[OpportunityDifficulty] = mapped_column(
        SqlEnum(
            OpportunityDifficulty,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="opportunity_difficulty",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=OpportunityDifficulty.MODERATE,
        server_default=OpportunityDifficulty.MODERATE.value,
    )
    decision: Mapped[OpportunityDecision] = mapped_column(
        SqlEnum(
            OpportunityDecision,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="opportunity_decision",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=OpportunityDecision.REVIEW,
        server_default=OpportunityDecision.REVIEW.value,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
