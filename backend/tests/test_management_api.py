from collections.abc import AsyncIterator, Iterator
from datetime import date
from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.imports import _statement_to_csv
from app.database.base import Base
from app.database.session import get_database_session
from app.main import app
from app.models import (
    CategorisationRule,
    Category,
    Expense,
    ImportBatch,
    Merchant,
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
async def test_transaction_rule_and_category_management(session: Session) -> None:
    category = Category(name="Shopping")
    merchant = Merchant(name="Example Merchant")
    batch = ImportBatch(
        source_filename="example.csv",
        source_type="csv",
        total_rows=1,
        processing_status="completed",
    )
    rule = CategorisationRule(match_pattern="SHOP", category=category, priority=10)
    expense = Expense(
        transaction_date=date(2026, 7, 24),
        description="Example shop",
        normalised_description="EXAMPLE SHOP",
        amount=1200,
        currency="GBP",
        import_batch=batch,
        merchant=merchant,
        category=category,
        status=TransactionStatus.NEEDS_REVIEW,
    )
    session.add_all([rule, expense])
    session.commit()

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            transactions = await client.get("/api/transactions?search=shop")
            filtered_transactions = await client.get(
                "/api/transactions",
                params={
                    "search": "merchant",
                    "status": "needs_review",
                    "category_id": category.id,
                    "merchant_id": merchant.id,
                    "import_batch_id": batch.id,
                    "currency": "gbp",
                    "date_from": "2026-07-01",
                    "date_to": "2026-07-31",
                    "limit": 1,
                    "offset": 0,
                },
            )
            bulk = await client.patch(
                "/api/transactions/bulk",
                json={"transaction_ids": [expense.id], "category_id": category.id},
            )
            rules = await client.get("/api/rules")
            rule_update = await client.patch(
                f"/api/rules/{rule.id}",
                json={"priority": 99, "enabled": False},
            )
            category_create = await client.post(
                "/api/categories",
                json={"name": "Temporary"},
            )
            category_delete = await client.delete(f"/api/categories/{category_create.json()['id']}")
    finally:
        app.dependency_overrides.clear()

    assert transactions.json()["total"] == 1
    assert filtered_transactions.json()["total"] == 1
    assert filtered_transactions.json()["limit"] == 1
    assert bulk.json() == {"updated": 1}
    assert rules.json()["items"][0]["match_pattern"] == "SHOP"
    assert rule_update.json()["priority"] == 99
    assert rule_update.json()["enabled"] is False
    assert category_create.status_code == 201
    assert category_delete.status_code == 204


@pytest.mark.anyio
async def test_dashboard_recurring_and_exports(session: Session) -> None:
    current = date(2025, 5, 15)
    category = Category(name="Subscriptions")
    session.add_all(
        [
            Expense(
                transaction_date=date(2025, 3, 15),
                description="Stream Co",
                normalised_description="STREAM CO",
                amount=-999,
                currency="GBP",
                category=category,
                status=TransactionStatus.CATEGORISED,
            ),
            Expense(
                transaction_date=date(2025, 4, 15),
                description="Stream Co",
                normalised_description="STREAM CO",
                amount=-1049,
                currency="GBP",
                category=category,
                status=TransactionStatus.CATEGORISED,
            ),
            Expense(
                transaction_date=current,
                description="Stream Co",
                normalised_description="STREAM CO",
                amount=-1025,
                currency="GBP",
                category=category,
                status=TransactionStatus.CATEGORISED,
            ),
            Expense(
                transaction_date=date(2025, 3, 1),
                description="Irregular Shop",
                normalised_description="IRREGULAR SHOP",
                amount=-500,
                currency="GBP",
                category=category,
                status=TransactionStatus.CATEGORISED,
            ),
            Expense(
                transaction_date=date(2025, 3, 3),
                description="Irregular Shop",
                normalised_description="IRREGULAR SHOP",
                amount=-500,
                currency="GBP",
                category=category,
                status=TransactionStatus.CATEGORISED,
            ),
            Expense(
                transaction_date=date(2025, 3, 20),
                description="Irregular Shop",
                normalised_description="IRREGULAR SHOP",
                amount=-500,
                currency="GBP",
                category=category,
                status=TransactionStatus.CATEGORISED,
            ),
        ]
    )
    session.commit()

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            dashboard = await client.get("/api/dashboard?currency=GBP&month=2025-05-01")
            recurring = await client.get(
                "/api/reports/recurring?currency=GBP&date_from=2025-03-01&date_to=2025-05-31"
            )
            csv_export = await client.get(
                "/api/reports/export"
                "?format=csv&currency=GBP&date_from=2025-05-01&date_to=2025-05-31"
            )
            excel_export = await client.get(
                "/api/reports/export"
                "?format=xlsx&currency=GBP&date_from=2025-05-01&date_to=2025-05-31"
            )
    finally:
        app.dependency_overrides.clear()

    assert dashboard.json()["spending"] == 1025
    assert dashboard.json()["month"] == "2025-05"
    assert recurring.json()["items"][0] == {
        "description": "STREAM CO",
        "currency": "GBP",
        "average_amount": 1024,
        "occurrence_count": 3,
        "cadence": "monthly",
        "typical_interval_days": 30,
        "last_seen": "2025-05-15",
    }
    assert csv_export.headers["content-type"].startswith("text/csv")
    assert csv_export.text.count("Stream Co") == 1
    assert excel_export.content.startswith(b"PK")


def test_excel_statement_is_converted_to_csv() -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["Date", "Description", "Amount", "Currency"])
    worksheet.append(["2026-07-24", "Coffee", "3.50", "GBP"])
    output = BytesIO()
    workbook.save(output)

    converted = _statement_to_csv(output.getvalue(), ".xlsx")

    assert "Date,Description,Amount,Currency" in converted
    assert "2026-07-24,Coffee,3.50,GBP" in converted
