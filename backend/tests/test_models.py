from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import (
    AllowanceType,
    CategorisationRule,
    Category,
    Commitment,
    CycleAllowance,
    Expense,
    ImportBatch,
    Merchant,
    PaymentCycle,
    PaymentCycleStatus,
    SpendingPriority,
    TransactionStatus,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def test_expense_category_and_rule_are_persisted(session: Session) -> None:
    import_batch = ImportBatch(
        source_filename="current-account.csv",
        source_type="csv",
        total_rows=1,
    )
    merchant = Merchant(name="Tesco")
    category = Category(name="Groceries")
    rule = CategorisationRule(
        match_pattern="TESCO",
        category=category,
        priority=100,
    )
    expense = Expense(
        transaction_date=date(2026, 7, 24),
        description="Tesco Stores",
        normalised_description="TESCO STORES",
        amount=2599,
        currency="GBP",
        import_batch=import_batch,
        merchant=merchant,
        category=category,
        matched_rule=rule,
        status=TransactionStatus.CATEGORISED,
        categorisation_source="rule",
        confidence_score=Decimal("0.9500"),
    )
    session.add_all([rule, expense])
    session.commit()

    assert expense.id is not None
    assert expense.created_at is not None
    assert expense.updated_at is not None
    assert expense.import_batch is import_batch
    assert expense.merchant is merchant
    assert expense.category is category
    assert expense.matched_rule is rule
    assert expense.status is TransactionStatus.CATEGORISED
    assert category.rules == [rule]
    assert rule.matched_expenses == [expense]


def test_category_can_have_a_parent(session: Session) -> None:
    parent = Category(name="Food")
    child = Category(name="Restaurants", parent=parent)
    session.add(child)
    session.commit()

    assert child.parent_category_id == parent.id
    assert parent.children == [child]


def test_confidence_score_must_be_between_zero_and_one(session: Session) -> None:
    session.add(
        Expense(
            transaction_date=date(2026, 7, 24),
            description="Invalid confidence",
            normalised_description="INVALID CONFIDENCE",
            amount=100,
            currency="GBP",
            confidence_score=Decimal("1.1000"),
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_unmatched_expense_can_be_queued_for_review(session: Session) -> None:
    expense = Expense(
        transaction_date=date(2026, 7, 24),
        description="Unknown card payment",
        normalised_description="UNKNOWN CARD PAYMENT",
        amount=1000,
        currency="GBP",
        status=TransactionStatus.NEEDS_REVIEW,
    )
    session.add(expense)
    session.commit()

    assert expense.category_id is None
    assert expense.matched_rule_id is None
    assert expense.status is TransactionStatus.NEEDS_REVIEW


def test_safe_spending_plan_is_persisted(session: Session) -> None:
    category = Category(
        name="Housing",
        default_priority=SpendingPriority.PROTECTED,
    )
    cycle = PaymentCycle(
        name="Universal Credit",
        start_date=date(2026, 7, 25),
        next_payment_date=date(2026, 8, 25),
        expected_income_amount=80000,
        currency="GBP",
        opening_balance=31000,
        current_balance=31000,
        status=PaymentCycleStatus.ACTIVE,
    )
    commitment = Commitment(
        payment_cycle=cycle,
        name="Rent",
        amount=16500,
        currency="GBP",
        due_date=date(2026, 8, 1),
        priority=SpendingPriority.PROTECTED,
        category=category,
    )
    allowance = CycleAllowance(
        payment_cycle=cycle,
        name="Food and transport",
        allowance_type=AllowanceType.FOOD,
        amount=9000,
        priority=SpendingPriority.ESSENTIAL,
    )
    expense = Expense(
        transaction_date=date(2026, 7, 26),
        description="Weekly food shop",
        normalised_description="WEEKLY FOOD SHOP",
        amount=-2500,
        currency="GBP",
        payment_cycle=cycle,
        priority_override=SpendingPriority.ESSENTIAL,
    )
    session.add_all([commitment, allowance, expense])
    session.commit()

    assert category.default_priority is SpendingPriority.PROTECTED
    assert cycle.commitments == [commitment]
    assert cycle.allowances == [allowance]
    assert cycle.expenses == [expense]
    assert expense.priority_override is SpendingPriority.ESSENTIAL


def test_deleting_payment_cycle_removes_plan_but_keeps_expense(session: Session) -> None:
    cycle = PaymentCycle(
        start_date=date(2026, 7, 25),
        next_payment_date=date(2026, 8, 25),
        expected_income_amount=80000,
        currency="GBP",
        opening_balance=31000,
    )
    expense = Expense(
        transaction_date=date(2026, 7, 26),
        description="Weekly food shop",
        normalised_description="WEEKLY FOOD SHOP",
        amount=-2500,
        currency="GBP",
        payment_cycle=cycle,
    )
    cycle.commitments.append(
        Commitment(
            name="Rent",
            amount=16500,
            currency="GBP",
            due_date=date(2026, 8, 1),
        )
    )
    session.add(expense)
    session.commit()

    session.delete(cycle)
    session.commit()
    session.refresh(expense)

    assert expense.payment_cycle_id is None
    assert session.query(Commitment).count() == 0
