from collections.abc import AsyncIterator, Iterator
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_database_session
from app.main import app
from app.models import CategorisationRule, Category, Expense, Merchant, TransactionStatus
from app.services.review_resolution_service import resolve_review


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
async def test_review_correction_assigns_category_and_saves_rule(session: Session) -> None:
    category = Category(name="Groceries")
    merchant = Merchant(name="Tesco")
    expense = Expense(
        transaction_date=date(2026, 7, 24),
        description="Tesco Stores",
        normalised_description="TESCO STORES",
        amount=2599,
        currency="GBP",
        merchant=merchant,
        status=TransactionStatus.NEEDS_REVIEW,
    )
    session.add_all([category, expense])
    session.commit()

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                f"/api/review-queue/{expense.id}/resolve",
                json={
                    "category_id": category.id,
                    "save_rule": True,
                    "match_pattern": "TESCO",
                    "priority": 100,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    rule = session.scalar(select(CategorisationRule))
    session.refresh(expense)
    assert rule is not None
    assert rule.match_pattern == "TESCO"
    assert rule.priority == 100
    assert expense.category is category
    assert expense.matched_rule is rule
    assert expense.status is TransactionStatus.CATEGORISED
    assert expense.categorisation_source == "manual"
    assert response.json()["rule_id"] == rule.id


@pytest.mark.anyio
async def test_resolving_completed_expense_returns_conflict(session: Session) -> None:
    category = Category(name="Travel")
    expense = Expense(
        transaction_date=date(2026, 7, 24),
        description="Train",
        normalised_description="TRAIN",
        amount=5000,
        currency="GBP",
        category=category,
        status=TransactionStatus.CATEGORISED,
    )
    session.add(expense)
    session.commit()

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                f"/api/review-queue/{expense.id}/resolve",
                json={"category_id": category.id},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_correction_updates_an_existing_rule(session: Session) -> None:
    old_category = Category(name="Old")
    new_category = Category(name="New")
    existing_rule = CategorisationRule(
        match_pattern="TESCO",
        category=old_category,
        priority=1,
        enabled=False,
    )
    expense = Expense(
        transaction_date=date(2026, 7, 24),
        description="Tesco",
        normalised_description="TESCO",
        amount=100,
        currency="GBP",
        status=TransactionStatus.NEEDS_REVIEW,
    )
    session.add_all([existing_rule, new_category, expense])
    session.commit()

    resolution = resolve_review(
        session,
        expense_id=expense.id,
        category_id=new_category.id,
        save_rule=True,
        match_pattern="tesco",
        priority=50,
    )

    assert resolution.rule_id == existing_rule.id
    assert existing_rule.category is new_category
    assert existing_rule.priority == 50
    assert existing_rule.enabled is True
    assert len(session.scalars(select(CategorisationRule)).all()) == 1
