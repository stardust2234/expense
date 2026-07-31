from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import (
    Category,
    Commitment,
    CommitmentStatus,
    Expense,
    Merchant,
    MerchantAlias,
    PaymentCycle,
    TransactionStatus,
)
from app.services.commitment_reconciliation import reconcile_pending_commitments


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
    with Session(engine, expire_on_commit=False) as database_session:
        yield database_session


def _cycle(name: str = "July") -> PaymentCycle:
    return PaymentCycle(
        name=name,
        start_date=date(2026, 6, 25),
        end_date=date(2026, 8, 1),
        next_payment_date=date(2026, 7, 25),
        expected_income_amount=90014,
        currency="GBP",
        opening_balance=90014,
    )


def _expense(
    cycle: PaymentCycle,
    *,
    amount: int = -4742,
    transaction_date: date = date(2026, 6, 29),
    currency: str = "GBP",
    description: str = "E.ON NEXT",
    category: Category | None = None,
    merchant: Merchant | None = None,
) -> Expense:
    return Expense(
        payment_cycle=cycle,
        transaction_date=transaction_date,
        description=description,
        normalised_description=description,
        amount=amount,
        currency=currency,
        category=category,
        merchant=merchant,
        status=TransactionStatus.CATEGORISED,
    )


def test_matches_same_cycle_category_amount_currency_and_near_date(
    session: Session,
) -> None:
    cycle = _cycle()
    category = Category(name="Utilities")
    expense = _expense(cycle, category=category)
    commitment = Commitment(
        payment_cycle=cycle,
        name="E.on",
        amount=4742,
        currency="GBP",
        due_date=date(2026, 6, 29),
        category=category,
    )
    session.add_all([expense, commitment])
    session.commit()

    result = reconcile_pending_commitments(session)

    assert result.matched == 1
    assert commitment.status is CommitmentStatus.PAID
    assert commitment.matched_expense_id == expense.id


def test_backfills_expense_link_for_paid_commitment(session: Session) -> None:
    cycle = _cycle()
    category = Category(name="Utilities")
    expense = _expense(cycle, category=category)
    commitment = Commitment(
        payment_cycle=cycle,
        name="E.on",
        amount=4742,
        currency="GBP",
        due_date=date(2026, 6, 29),
        category=category,
        status=CommitmentStatus.PAID,
    )
    session.add_all([expense, commitment])
    session.commit()

    result = reconcile_pending_commitments(session)

    assert result.matched == 1
    assert commitment.status is CommitmentStatus.PAID
    assert commitment.matched_expense_id == expense.id


def test_uses_merchant_alias_when_commitment_has_no_category(session: Session) -> None:
    cycle = _cycle()
    merchant = Merchant(
        name="Amazon",
        aliases=[MerchantAlias(pattern="AMZN MKTP")],
    )
    expense = _expense(
        cycle,
        amount=-2397,
        description="Card purchase",
        merchant=merchant,
    )
    commitment = Commitment(
        payment_cycle=cycle,
        name="AMZN MKTP",
        amount=2397,
        currency="GBP",
        due_date=date(2026, 6, 29),
    )
    session.add_all([expense, commitment])
    session.commit()

    result = reconcile_pending_commitments(session)

    assert result.matched == 1
    assert commitment.matched_expense_id == expense.id


@pytest.mark.parametrize(
    ("expense_changes",),
    [
        ({"amount": -4743},),
        ({"currency": "EUR"},),
        ({"transaction_date": date(2026, 6, 14)},),
    ],
)
def test_rejects_incompatible_transactions(
    session: Session,
    expense_changes: dict[str, object],
) -> None:
    cycle = _cycle()
    category = Category(name="Utilities")
    expense = _expense(cycle, category=category, **expense_changes)
    commitment = Commitment(
        payment_cycle=cycle,
        name="E.on",
        amount=4742,
        currency="GBP",
        due_date=date(2026, 6, 29),
        category=category,
    )
    session.add_all([expense, commitment])
    session.commit()

    result = reconcile_pending_commitments(session)

    assert result.matched == 0
    assert commitment.status is CommitmentStatus.PENDING
    assert commitment.matched_expense_id is None


def test_rejects_different_payment_cycle_or_category(session: Session) -> None:
    cycle = _cycle()
    other_cycle = PaymentCycle(
        name="August",
        start_date=date(2026, 7, 25),
        end_date=date(2026, 9, 1),
        next_payment_date=date(2026, 8, 25),
        expected_income_amount=90014,
        currency="GBP",
        opening_balance=90014,
    )
    utilities = Category(name="Utilities")
    housing = Category(name="Housing")
    wrong_cycle = _expense(other_cycle, category=utilities)
    wrong_category = _expense(cycle, category=housing)
    commitment = Commitment(
        payment_cycle=cycle,
        name="E.on",
        amount=4742,
        currency="GBP",
        due_date=date(2026, 6, 29),
        category=utilities,
    )
    session.add_all([wrong_cycle, wrong_category, commitment])
    session.commit()

    result = reconcile_pending_commitments(session)

    assert result.matched == 0
    assert commitment.status is CommitmentStatus.PENDING


def test_category_match_still_requires_recognisable_payee(session: Session) -> None:
    cycle = _cycle()
    category = Category(name="Utilities")
    expense = _expense(cycle, category=category, description="UNRELATED COMPANY")
    commitment = Commitment(
        payment_cycle=cycle,
        name="E.on",
        amount=4742,
        currency="GBP",
        due_date=date(2026, 6, 29),
        category=category,
    )
    session.add_all([expense, commitment])
    session.commit()

    result = reconcile_pending_commitments(session)

    assert result.matched == 0
    assert commitment.status is CommitmentStatus.PENDING


def test_leaves_equally_ranked_candidates_ambiguous(session: Session) -> None:
    cycle = _cycle()
    category = Category(name="Utilities")
    expense_one = _expense(cycle, category=category)
    expense_two = _expense(cycle, category=category)
    commitment = Commitment(
        payment_cycle=cycle,
        name="E.on",
        amount=4742,
        currency="GBP",
        due_date=date(2026, 6, 29),
        category=category,
    )
    session.add_all([expense_one, expense_two, commitment])
    session.commit()

    result = reconcile_pending_commitments(session)

    assert result.ambiguous == 1
    assert commitment.status is CommitmentStatus.PENDING
    assert commitment.matched_expense_id is None
