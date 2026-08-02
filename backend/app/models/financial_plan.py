from __future__ import annotations

import calendar
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.workspace_owned import WorkspaceOwned

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.expense import Expense


class SpendingPriority(str, Enum):
    PROTECTED = "protected"
    ESSENTIAL = "essential"
    ADJUSTABLE = "adjustable"
    OPTIONAL = "optional"
    IRREGULAR_ESSENTIAL = "irregular_essential"
    TRANSFER = "transfer"


class PaymentCycleStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    CLOSED = "closed"


class CommitmentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    SKIPPED = "skipped"


class AllowanceType(str, Enum):
    FOOD = "food"
    TRANSPORT = "transport"
    IRREGULAR_COST = "irregular_cost"
    EMERGENCY = "emergency"
    CUSTOM = "custom"


class PaymentCycle(WorkspaceOwned, Base):
    __tablename__ = "payment_cycles"
    __table_args__ = (
        CheckConstraint(
            "end_date > start_date",
            name="ck_payment_cycles_date_order",
        ),
        CheckConstraint(
            "next_payment_date >= date(start_date, '-7 days') AND next_payment_date < end_date",
            name="ck_payment_cycles_payment_within_cycle",
        ),
        CheckConstraint(
            "expected_income_amount >= 0",
            name="ck_payment_cycles_expected_income_nonnegative",
        ),
        CheckConstraint(
            "length(currency) = 3",
            name="ck_payment_cycles_currency_length",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    next_payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expected_income_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    opening_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    current_balance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[PaymentCycleStatus] = mapped_column(
        SqlEnum(
            PaymentCycleStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="payment_cycle_status",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=PaymentCycleStatus.PLANNED,
        server_default=PaymentCycleStatus.PLANNED.value,
        index=True,
    )
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

    expenses: Mapped[list[Expense]] = relationship(
        foreign_keys="Expense.payment_cycle_id",
        back_populates="payment_cycle",
    )
    commitments: Mapped[list[Commitment]] = relationship(
        back_populates="payment_cycle",
        cascade="all, delete-orphan",
    )
    allowances: Mapped[list[CycleAllowance]] = relationship(
        back_populates="payment_cycle",
        cascade="all, delete-orphan",
    )


class Commitment(WorkspaceOwned, Base):
    __tablename__ = "commitments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_commitments_amount_nonnegative"),
        CheckConstraint("length(currency) = 3", name="ck_commitments_currency_length"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_cycle_id: Mapped[int] = mapped_column(
        ForeignKey("payment_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    priority: Mapped[SpendingPriority] = mapped_column(
        SqlEnum(
            SpendingPriority,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="commitment_spending_priority",
            values_callable=lambda priorities: [priority.value for priority in priorities],
        ),
        nullable=False,
        default=SpendingPriority.PROTECTED,
        server_default=SpendingPriority.PROTECTED.value,
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[CommitmentStatus] = mapped_column(
        SqlEnum(
            CommitmentStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="commitment_status",
            values_callable=lambda statuses: [status.value for status in statuses],
        ),
        nullable=False,
        default=CommitmentStatus.PENDING,
        server_default=CommitmentStatus.PENDING.value,
        index=True,
    )
    recurrence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inference_identity_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    matched_expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
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

    payment_cycle: Mapped[PaymentCycle] = relationship(back_populates="commitments")
    category: Mapped[Category | None] = relationship(back_populates="commitments")
    matched_expense: Mapped[Expense | None] = relationship(
        foreign_keys=[matched_expense_id],
        back_populates="matched_commitment",
    )

    @property
    def funding_payment_date(self) -> date:
        """The most recent monthly benefit payment on or before the bill."""
        payment_date = self.payment_cycle.next_payment_date
        if self.due_date >= payment_date:
            return payment_date
        previous_month = payment_date.month - 1 or 12
        previous_year = payment_date.year - (1 if payment_date.month == 1 else 0)
        return date(
            previous_year,
            previous_month,
            min(
                payment_date.day,
                calendar.monthrange(previous_year, previous_month)[1],
            ),
        )


class CycleAllowance(WorkspaceOwned, Base):
    __tablename__ = "cycle_allowances"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_cycle_allowances_amount_nonnegative"),
        UniqueConstraint(
            "payment_cycle_id",
            "allowance_type",
            "category_id",
            name="uq_cycle_allowance_type_category",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_cycle_id: Mapped[int] = mapped_column(
        ForeignKey("payment_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    allowance_type: Mapped[AllowanceType] = mapped_column(
        SqlEnum(
            AllowanceType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="allowance_type",
            values_callable=lambda allowance_types: [
                allowance_type.value for allowance_type in allowance_types
            ],
        ),
        nullable=False,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[SpendingPriority] = mapped_column(
        SqlEnum(
            SpendingPriority,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            name="allowance_spending_priority",
            values_callable=lambda priorities: [priority.value for priority in priorities],
        ),
        nullable=False,
        default=SpendingPriority.ESSENTIAL,
        server_default=SpendingPriority.ESSENTIAL.value,
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    inference_identity_key: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    payment_cycle: Mapped[PaymentCycle] = relationship(back_populates="allowances")
    category: Mapped[Category | None] = relationship(back_populates="allowances")
