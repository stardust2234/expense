from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import (
    CategorisationRule,
    Category,
    Expense,
    ImportBatch,
    Merchant,
    RawTransaction,
    TransactionStatus,
)
from app.services.transaction_processor import (
    categorise_normalised_transactions,
    normalise_pending_transactions,
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


def add_raw_transaction(
    session: Session,
    *,
    row_number: int,
    description: str,
    amount: str = "25.99",
) -> RawTransaction:
    batch = session.scalar(select(ImportBatch))
    if batch is None:
        batch = ImportBatch(
            source_filename="transactions.csv",
            source_type="csv",
            total_rows=1,
        )
        session.add(batch)

    raw_transaction = RawTransaction(
        import_batch=batch,
        source_row_number=row_number,
        raw_data={
            "Date": "2026-07-24",
            "Description": description,
            "Amount": amount,
            "Currency": "GBP",
        },
    )
    session.add(raw_transaction)
    session.commit()
    return raw_transaction


def test_normalises_pending_rows_idempotently(session: Session) -> None:
    raw_transaction = add_raw_transaction(
        session,
        row_number=2,
        description=" Tesco Stores 0123 ",
    )

    first_result = normalise_pending_transactions(session)
    second_result = normalise_pending_transactions(session)
    expense = session.scalar(select(Expense))

    assert first_result.normalised == 1
    assert first_result.failed == 0
    assert second_result.normalised == 0
    assert expense is not None
    assert expense.raw_transaction is raw_transaction
    assert expense.normalised_description == "TESCO STORES 0123"
    assert expense.status is TransactionStatus.NORMALISED
    assert len(session.scalars(select(Expense)).all()) == 1


def test_records_normalisation_errors_without_creating_expense(session: Session) -> None:
    raw_transaction = add_raw_transaction(
        session,
        row_number=2,
        description="Coffee",
        amount="not-money",
    )

    result = normalise_pending_transactions(session)

    assert result.failed == 1
    assert raw_transaction.normalisation_error is not None
    assert session.scalar(select(Expense)) is None


def test_identifies_merchant_and_applies_highest_priority_rule(session: Session) -> None:
    add_raw_transaction(
        session,
        row_number=2,
        description="Tesco Express London",
    )
    groceries = Category(name="Groceries")
    other = Category(name="Other")
    merchant = Merchant(name="Tesco Express")
    low_priority_rule = CategorisationRule(
        match_pattern="TESCO",
        category=other,
        priority=10,
    )
    high_priority_rule = CategorisationRule(
        match_pattern="EXPRESS",
        category=groceries,
        priority=100,
    )
    session.add_all([merchant, low_priority_rule, high_priority_rule])
    session.commit()
    normalise_pending_transactions(session)

    result = categorise_normalised_transactions(session)
    expense = session.scalar(select(Expense))

    assert result.categorised == 1
    assert expense is not None
    assert expense.merchant is merchant
    assert expense.category is groceries
    assert expense.matched_rule is high_priority_rule
    assert expense.status is TransactionStatus.CATEGORISED
    assert expense.categorisation_source == "rule"


def test_unmatched_expense_is_sent_to_review(session: Session) -> None:
    add_raw_transaction(
        session,
        row_number=2,
        description="Unknown payment",
    )
    normalise_pending_transactions(session)

    result = categorise_normalised_transactions(session)
    expense = session.scalar(select(Expense))

    assert result.needs_review == 1
    assert expense is not None
    assert expense.status is TransactionStatus.NEEDS_REVIEW
    assert expense.category_id is None
