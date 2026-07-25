from collections.abc import AsyncIterator, Iterator
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_database_session
from app.main import app
from app.models import (
    Category,
    Expense,
    ImportBatch,
    Merchant,
    RawTransaction,
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
    with Session(engine, expire_on_commit=False) as database_session:
        yield database_session


@pytest.mark.anyio
async def test_review_queue_returns_only_pending_items(session: Session) -> None:
    batch = ImportBatch(
        source_filename="current-account.csv",
        source_type="csv",
        total_rows=1,
    )
    raw_transaction = RawTransaction(
        import_batch=batch,
        source_row_number=2,
        raw_data={
            "Date": "2026-07-24",
            "Description": "Unknown payment",
            "Amount": "12.50",
            "Currency": "GBP",
        },
    )
    merchant = Merchant(name="Possible Merchant")
    category = Category(name="Already categorised")
    pending = Expense(
        transaction_date=date(2026, 7, 24),
        description="Unknown payment",
        normalised_description="UNKNOWN PAYMENT",
        amount=1250,
        currency="GBP",
        import_batch=batch,
        raw_transaction=raw_transaction,
        merchant=merchant,
        status=TransactionStatus.NEEDS_REVIEW,
    )
    completed = Expense(
        transaction_date=date(2026, 7, 23),
        description="Known payment",
        normalised_description="KNOWN PAYMENT",
        amount=500,
        currency="GBP",
        category=category,
        status=TransactionStatus.CATEGORISED,
    )
    session.add_all([pending, completed])
    session.commit()

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/review-queue?limit=10&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 10
    assert payload["offset"] == 0
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == pending.id
    assert payload["items"][0]["merchant_name"] == "Possible Merchant"
    assert payload["items"][0]["source_filename"] == "current-account.csv"
    assert payload["items"][0]["source_row_number"] == 2
    assert payload["items"][0]["raw_data"]["Amount"] == "12.50"


@pytest.mark.anyio
async def test_review_queue_validates_pagination(session: Session) -> None:
    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/review-queue?limit=101")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
