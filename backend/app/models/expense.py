from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.workspace_owned import WorkspaceOwned

if TYPE_CHECKING:
    from app.models.categorisation_rule import CategorisationRule
    from app.models.category import Category
    from app.models.financial_plan import Commitment, PaymentCycle
    from app.models.import_batch import ImportBatch
    from app.models.merchant import Merchant
    from app.models.raw_transaction import RawTransaction

from app.models.financial_plan import SpendingPriority


class TransactionStatus(str, Enum):
    IMPORTED = "imported"
    NORMALISED = "normalised"
    MERCHANT_IDENTIFIED = "merchant_identified"
    CATEGORISED = "categorised"
    NEEDS_REVIEW = "needs_review"


class Expense(WorkspaceOwned, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("length(currency) = 3", name="ck_expenses_currency_length"),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_expenses_confidence_score_range",
        ),
        UniqueConstraint(
            "raw_transaction_id",
            name="uq_expenses_raw_transaction_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    normalised_description: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    # Store money in the currency's minor unit (for example, pence) to avoid float rounding.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payment_cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_cycles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    raw_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "raw_transactions.id",
            name="fk_expenses_raw_transaction_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    matched_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("categorisation_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        SqlEnum(
            TransactionStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="transaction_status",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=TransactionStatus.IMPORTED,
        server_default=TransactionStatus.IMPORTED.value,
        index=True,
    )
    categorisation_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    priority_override: Mapped[SpendingPriority | None] = mapped_column(
        SqlEnum(
            SpendingPriority,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="expense_spending_priority",
            values_callable=lambda priorities: [priority.value for priority in priorities],
        ),
        nullable=True,
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    import_batch: Mapped[ImportBatch | None] = relationship(back_populates="expenses")
    raw_transaction: Mapped[RawTransaction | None] = relationship(
        foreign_keys=[raw_transaction_id],
        back_populates="expense",
    )
    merchant: Mapped[Merchant | None] = relationship(back_populates="expenses")
    category: Mapped[Category | None] = relationship(back_populates="expenses")
    matched_rule: Mapped[CategorisationRule | None] = relationship(
        back_populates="matched_expenses"
    )
    payment_cycle: Mapped[PaymentCycle | None] = relationship(
        foreign_keys=[payment_cycle_id],
        back_populates="expenses",
    )
    matched_commitment: Mapped[Commitment | None] = relationship(
        foreign_keys="Commitment.matched_expense_id",
        back_populates="matched_expense",
    )
