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
from app.models import Category, Commitment, Expense, PaymentCycle, SpendingPriority
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
        transaction_date=date(2026, 8, 26),
        description="Included",
        normalised_description="INCLUDED",
        amount=-1000,
        currency="GBP",
    )
    excluded = Expense(
        transaction_date=date(2026, 9, 1),
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
            "next_payment_date": "2026-08-20",
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

    after_payment_response = await client.post(
        f"/api/payment-cycles/{first_response.json()['id']}/commitments",
        json={
            "name": "Month-end bill",
            "amount": 1000,
            "due_date": "2026-06-30",
        },
    )
    assert after_payment_response.status_code == 201
    assert after_payment_response.json()["funding_payment_date"] == "2026-06-29"


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
    payment_date_response = await client.patch(
        f"/api/payment-cycles/{cycle_id}",
        json={"next_payment_date": "2026-08-15"},
    )
    commitment_null_response = await client.patch(
        f"/api/commitments/{commitment_id}",
        json={"amount": None},
    )

    assert null_response.status_code == 422
    assert payment_date_response.status_code == 200
    assert payment_date_response.json()["end_date"] == "2026-09-01"
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


@pytest.mark.anyio
async def test_forecast_rolls_to_next_income_and_derives_opening_balance(
    client: AsyncClient,
    session: Session,
) -> None:
    expense = Expense(
        transaction_date=date(2026, 7, 10),
        description="Food",
        normalised_description="FOOD",
        amount=-10000,
        currency="GBP",
        status=TransactionStatus.NEEDS_REVIEW,
    )
    session.add(expense)
    session.commit()
    july = await client.post(
        "/api/payment-cycles",
        json={
            "next_payment_date": "2026-07-29",
            "expected_income_amount": 90000,
            "currency": "GBP",
            "opening_balance": 100000,
            "current_balance": None,
            "status": "active",
        },
    )
    august = await client.post(
        "/api/payment-cycles",
        json={
            "next_payment_date": "2026-08-29",
            "expected_income_amount": 91000,
            "currency": "GBP",
            "opening_balance": 0,
            "status": "planned",
        },
    )
    commitment = await client.post(
        f"/api/payment-cycles/{august.json()['id']}/commitments",
        json={"name": "Rent", "amount": 20000, "due_date": "2026-08-10"},
    )
    assert commitment.status_code == 201

    response = await client.get(
        f"/api/payment-cycles/{july.json()['id']}/forecast?as_of=2026-07-31"
    )

    assert response.status_code == 200
    forecast = response.json()
    assert forecast["next_payment_date"] == "2026-08-29"
    assert forecast["usable_balance"] == 90000
    assert forecast["pending_commitments"] == 20000


@pytest.mark.anyio
async def test_plan_inference_preview_is_read_only_and_confirmation_is_selective(
    client: AsyncClient,
    session: Session,
) -> None:
    income_root = Category(name="Income")
    benefits = Category(name="Benefits", parent=income_root)
    housing = Category(name="Housing")
    rent = Category(
        name="Rent",
        parent=housing,
        default_priority=SpendingPriority.PROTECTED,
    )
    groceries = Category(
        name="Groceries",
        default_priority=SpendingPriority.ESSENTIAL,
    )
    rows = [
        (date(2026, 5, 29), "Benefit", 90000, benefits),
        (date(2026, 6, 29), "Benefit", 90100, benefits),
        (date(2026, 7, 29), "Benefit", 90000, benefits),
        (date(2026, 5, 27), "Rent", -50000, rent),
        (date(2026, 6, 27), "Rent", -50000, rent),
        (date(2026, 7, 27), "Rent", -50000, rent),
        (date(2026, 5, 8), "Food shop one", -4500, groceries),
        (date(2026, 6, 12), "Food shop two", -5200, groceries),
        (date(2026, 7, 18), "Food shop three", -4800, groceries),
    ]
    session.add_all(
        [
            Expense(
                transaction_date=transaction_date,
                description=description,
                normalised_description=description.upper(),
                amount=amount,
                currency="GBP",
                category=category,
                status=TransactionStatus.CATEGORISED,
            )
            for transaction_date, description, amount, category in rows
        ]
    )
    session.commit()

    preview_response = await client.get(
        "/api/plan-inference/preview?target_month=2026-08-01&currency=GBP"
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert session.query(PaymentCycle).count() == 0
    assert preview["income"]["payment_date"] == "2026-08-29"
    assert len(preview["commitments"]) == 1
    assert len(preview["allowances"]) == 1

    confirm_response = await client.post(
        "/api/plan-inference/confirm",
        json={
            "target_month": "2026-08-01",
            "currency": "GBP",
            "opening_balance": 10000,
            "current_balance": 9000,
            "commitment_proposal_ids": [preview["commitments"][0]["proposal_id"]],
            "allowance_proposal_ids": [preview["allowances"][0]["proposal_id"]],
        },
    )

    assert confirm_response.status_code == 201
    confirmation = confirm_response.json()
    cycle = session.get(PaymentCycle, confirmation["payment_cycle_id"])
    assert cycle is not None
    assert cycle.start_date == date(2026, 8, 1)
    assert cycle.end_date == date(2026, 9, 1)
    assert cycle.next_payment_date == date(2026, 8, 29)
    assert cycle.expected_income_amount == 90000
    assert len(cycle.commitments) == 1
    assert cycle.commitments[0].due_date == date(2026, 8, 27)
    assert len(cycle.allowances) == 1
    assert cycle.allowances[0].amount == 4800
    cycle.commitments[0].amount = 49000
    session.commit()

    repeated = await client.post(
        "/api/plan-inference/confirm",
        json={
            "target_month": "2026-08-01",
            "currency": "GBP",
            "opening_balance": 1,
            "current_balance": 2,
            "commitment_proposal_ids": [preview["commitments"][0]["proposal_id"]],
            "allowance_proposal_ids": [],
        },
    )
    session.refresh(cycle)
    assert repeated.status_code == 201
    assert repeated.json()["created_cycle"] is False
    assert cycle.opening_balance == 10000
    assert cycle.current_balance == 9000
    assert cycle.expected_income_amount == 90000
    assert len(cycle.commitments) == 1
    assert cycle.commitments[0].amount == 49000


async def _count_cycles(client: AsyncClient) -> int:
    response = await client.get("/api/payment-cycles")
    return response.json()["total"]
