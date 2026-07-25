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
from app.models import Category, Commitment, Expense
from app.models.expense import TransactionStatus


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


@pytest.fixture
async def client(session: Session) -> AsyncIterator[AsyncClient]:
    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as api_client:
            yield api_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_payment_cycle_crud_and_pagination(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/payment-cycles",
        json={
            "name": "Universal Credit",
            "start_date": "2026-07-25",
            "next_payment_date": "2026-08-25",
            "expected_income_amount": 80000,
            "currency": "gbp",
            "opening_balance": 31000,
            "current_balance": 30000,
            "status": "active",
        },
    )
    assert create_response.status_code == 201
    cycle = create_response.json()
    assert cycle["currency"] == "GBP"
    assert cycle["status"] == "active"

    detail_response = await client.get(f"/api/payment-cycles/{cycle['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "Universal Credit"

    list_response = await client.get("/api/payment-cycles?limit=1&offset=0")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == cycle["id"]

    patch_response = await client.patch(
        f"/api/payment-cycles/{cycle['id']}",
        json={"current_balance": 27500, "name": "UC payment"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["current_balance"] == 27500
    assert patch_response.json()["name"] == "UC payment"

    delete_response = await client.delete(f"/api/payment-cycles/{cycle['id']}")
    assert delete_response.status_code == 204
    assert (await client.get(f"/api/payment-cycles/{cycle['id']}")).status_code == 404


@pytest.mark.anyio
async def test_creating_cycle_links_existing_transactions_in_its_date_window(
    client: AsyncClient,
    session: Session,
) -> None:
    included = Expense(
        transaction_date=date(2026, 7, 26),
        description="Included",
        normalised_description="INCLUDED",
        amount=-1000,
        currency="GBP",
    )
    excluded = Expense(
        transaction_date=date(2026, 8, 25),
        description="Next cycle",
        normalised_description="NEXT CYCLE",
        amount=-1000,
        currency="GBP",
    )
    session.add_all([included, excluded])
    session.commit()

    response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-07-25",
            "next_payment_date": "2026-08-25",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 31000,
        },
    )
    session.refresh(included)
    session.refresh(excluded)

    assert response.status_code == 201
    assert included.payment_cycle_id == response.json()["id"]
    assert excluded.payment_cycle_id is None


@pytest.mark.anyio
async def test_payment_cycles_cannot_overlap_in_the_same_currency(
    client: AsyncClient,
) -> None:
    first = {
        "start_date": "2026-07-25",
        "next_payment_date": "2026-08-25",
        "expected_income_amount": 80000,
        "currency": "GBP",
        "opening_balance": 31000,
    }
    assert (await client.post("/api/payment-cycles", json=first)).status_code == 201

    overlap_response = await client.post(
        "/api/payment-cycles",
        json={
            **first,
            "start_date": "2026-08-20",
            "next_payment_date": "2026-09-20",
        },
    )
    adjacent_response = await client.post(
        "/api/payment-cycles",
        json={
            **first,
            "start_date": "2026-08-25",
            "next_payment_date": "2026-09-25",
        },
    )

    assert overlap_response.status_code == 409
    assert "overlaps" in overlap_response.json()["detail"]
    assert adjacent_response.status_code == 201


@pytest.mark.anyio
async def test_commitment_crud_defaults_currency_and_accepts_category(
    client: AsyncClient,
    session: Session,
) -> None:
    category = Category(name="Housing")
    session.add(category)
    session.commit()
    cycle_response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-07-25",
            "next_payment_date": "2026-08-25",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 31000,
        },
    )
    cycle_id = cycle_response.json()["id"]

    create_response = await client.post(
        f"/api/payment-cycles/{cycle_id}/commitments",
        json={
            "name": "  August   rent ",
            "amount": 16500,
            "due_date": "2026-08-01",
            "category_id": category.id,
        },
    )
    assert create_response.status_code == 201
    commitment = create_response.json()
    assert commitment["name"] == "August rent"
    assert commitment["currency"] == "GBP"
    assert commitment["priority"] == "protected"
    assert commitment["status"] == "pending"

    list_response = await client.get(f"/api/payment-cycles/{cycle_id}/commitments")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    patch_response = await client.patch(
        f"/api/commitments/{commitment['id']}",
        json={"status": "paid", "category_id": None},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "paid"
    assert patch_response.json()["category_id"] is None

    delete_response = await client.delete(f"/api/commitments/{commitment['id']}")
    assert delete_response.status_code == 204
    assert session.query(Commitment).count() == 0


@pytest.mark.anyio
async def test_commitments_require_a_cycle_covering_the_due_date(
    client: AsyncClient,
) -> None:
    cycle_response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-07-25",
            "next_payment_date": "2026-08-25",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 31000,
        },
    )
    cycle_id = cycle_response.json()["id"]

    outside_response = await client.post(
        f"/api/payment-cycles/{cycle_id}/commitments",
        json={
            "name": "September rent",
            "amount": 16500,
            "currency": "GBP",
            "due_date": "2026-09-01",
        },
    )
    currency_response = await client.post(
        f"/api/payment-cycles/{cycle_id}/commitments",
        json={
            "name": "Euro bill",
            "amount": 1000,
            "currency": "EUR",
            "due_date": "2026-08-01",
        },
    )

    assert outside_response.status_code == 409
    assert "covers commitment due date" in outside_response.json()["detail"]
    assert currency_response.status_code == 409
    assert "EUR payment cycle" in currency_response.json()["detail"]
    assert await _count_cycles(client) == 1


@pytest.mark.anyio
async def test_commitment_due_date_selects_its_funding_cycle(
    client: AsyncClient,
) -> None:
    first_response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-05-29",
            "next_payment_date": "2026-06-29",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 80000,
        },
    )
    second_response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-06-29",
            "next_payment_date": "2026-07-29",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 80000,
        },
    )

    response = await client.post(
        f"/api/payment-cycles/{second_response.json()['id']}/commitments",
        json={
            "name": "Council tax",
            "amount": 1200,
            "due_date": "2026-06-28",
        },
    )

    assert response.status_code == 201
    assert response.json()["payment_cycle_id"] == first_response.json()["id"]
    assert response.json()["funding_payment_date"] == "2026-05-29"


@pytest.mark.anyio
async def test_monthly_commitment_is_generated_in_next_adjacent_cycle(
    client: AsyncClient,
) -> None:
    first_response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-05-29",
            "next_payment_date": "2026-06-29",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 80000,
        },
    )
    commitment_response = await client.post(
        f"/api/payment-cycles/{first_response.json()['id']}/commitments",
        json={
            "name": "Council tax",
            "amount": 1200,
            "due_date": "2026-06-28",
            "recurrence": "monthly",
        },
    )
    assert commitment_response.status_code == 201

    second_response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-06-29",
            "next_payment_date": "2026-07-29",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 80000,
        },
    )
    commitments_response = await client.get(
        f"/api/payment-cycles/{second_response.json()['id']}/commitments"
    )

    assert commitments_response.status_code == 200
    assert commitments_response.json()["items"] == [
        {
            **commitment_response.json(),
            "id": commitments_response.json()["items"][0]["id"],
            "payment_cycle_id": second_response.json()["id"],
            "funding_payment_date": "2026-06-29",
            "due_date": "2026-07-28",
            "status": "pending",
            "matched_expense_id": None,
            "created_at": commitments_response.json()["items"][0]["created_at"],
            "updated_at": commitments_response.json()["items"][0]["updated_at"],
        }
    ]


@pytest.mark.anyio
async def test_patch_rejects_null_required_fields_and_orphaned_commitment_dates(
    client: AsyncClient,
) -> None:
    cycle_response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-07-25",
            "next_payment_date": "2026-08-25",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 31000,
        },
    )
    cycle_id = cycle_response.json()["id"]
    commitment_response = await client.post(
        f"/api/payment-cycles/{cycle_id}/commitments",
        json={
            "name": "Rent",
            "amount": 16500,
            "due_date": "2026-08-20",
        },
    )
    commitment_id = commitment_response.json()["id"]

    null_response = await client.patch(
        f"/api/payment-cycles/{cycle_id}",
        json={"opening_balance": None},
    )
    shortened_response = await client.patch(
        f"/api/payment-cycles/{cycle_id}",
        json={"next_payment_date": "2026-08-15"},
    )
    commitment_null_response = await client.patch(
        f"/api/commitments/{commitment_id}",
        json={"amount": None},
    )

    assert null_response.status_code == 422
    assert shortened_response.status_code == 409
    assert "every commitment" in shortened_response.json()["detail"]
    assert commitment_null_response.status_code == 422


@pytest.mark.anyio
async def test_allowance_crud_and_safe_spending_forecast(
    client: AsyncClient,
    session: Session,
) -> None:
    groceries = Category(name="Groceries")
    session.add(groceries)
    session.commit()
    cycle_response = await client.post(
        "/api/payment-cycles",
        json={
            "start_date": "2026-07-25",
            "next_payment_date": "2026-08-22",
            "expected_income_amount": 80000,
            "currency": "GBP",
            "opening_balance": 35000,
            "current_balance": 31000,
            "status": "active",
        },
    )
    cycle_id = cycle_response.json()["id"]
    commitment_response = await client.post(
        f"/api/payment-cycles/{cycle_id}/commitments",
        json={"name": "Rent", "amount": 16500, "due_date": "2026-08-01"},
    )
    assert commitment_response.status_code == 201

    food_response = await client.post(
        f"/api/payment-cycles/{cycle_id}/allowances",
        json={
            "name": "Groceries",
            "allowance_type": "food",
            "amount": 9000,
            "category_id": groceries.id,
        },
    )
    reserve_response = await client.post(
        f"/api/payment-cycles/{cycle_id}/allowances",
        json={
            "name": "Irregular costs",
            "allowance_type": "irregular_cost",
            "amount": 2000,
            "priority": "irregular_essential",
        },
    )
    assert food_response.status_code == 201
    assert reserve_response.status_code == 201
    food_allowance = food_response.json()

    session.add(
        Expense(
            transaction_date=date(2026, 7, 26),
            description="Food shop",
            normalised_description="FOOD SHOP",
            amount=-3000,
            currency="GBP",
            category_id=groceries.id,
            payment_cycle_id=cycle_id,
            status=TransactionStatus.CATEGORISED,
        )
    )
    session.commit()

    forecast_response = await client.get(
        f"/api/payment-cycles/{cycle_id}/forecast?as_of=2026-07-26"
    )
    assert forecast_response.status_code == 200
    forecast = forecast_response.json()
    assert forecast["balance_source"] == "current"
    assert forecast["pending_commitments"] == 16500
    assert forecast["allowance_reserves"] == 8000
    assert forecast["safe_to_spend"] == 6500
    assert forecast["shortfall"] == 0
    assert forecast["allowances"][0]["spent_amount"] == 3000
    assert forecast["allowances"][0]["remaining_amount"] == 6000

    duplicate_response = await client.post(
        f"/api/payment-cycles/{cycle_id}/allowances",
        json={
            "name": "Duplicate grocery budget",
            "allowance_type": "custom",
            "amount": 1000,
            "category_id": groceries.id,
        },
    )
    assert duplicate_response.status_code == 409

    patch_response = await client.patch(
        f"/api/allowances/{food_allowance['id']}",
        json={"amount": 10000},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["amount"] == 10000
    detail_response = await client.get(f"/api/allowances/{food_allowance['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "Groceries"

    list_response = await client.get(f"/api/payment-cycles/{cycle_id}/allowances")
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 2

    delete_response = await client.delete(f"/api/allowances/{food_allowance['id']}")
    assert delete_response.status_code == 204


async def _count_cycles(client: AsyncClient) -> int:
    response = await client.get("/api/payment-cycles")
    return response.json()["total"]
