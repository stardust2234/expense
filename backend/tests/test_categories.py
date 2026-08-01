from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_database_session
from app.main import app
from app.models import Category, SpendingPriority


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
async def test_categories_are_flat_sorted_and_include_parent_ids(session: Session) -> None:
    food = Category(name="Food")
    restaurants = Category(name="restaurants", parent=food)
    travel = Category(name="Travel")
    session.add_all([travel, restaurants])
    session.commit()

    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/categories")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": food.id,
                "code": None,
                "name": "Food",
                "parent_category_id": None,
                "default_priority": "adjustable",
            },
            {
                "id": restaurants.id,
                "code": None,
                "name": "restaurants",
                "parent_category_id": food.id,
                "default_priority": "adjustable",
            },
            {
                "id": travel.id,
                "code": None,
                "name": "Travel",
                "parent_category_id": None,
                "default_priority": "adjustable",
            },
        ]
    }


@pytest.mark.anyio
async def test_categories_can_be_empty(session: Session) -> None:
    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/categories")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"items": []}


@pytest.mark.anyio
async def test_category_priority_can_be_created_and_updated(session: Session) -> None:
    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            created = await client.post(
                "/api/categories",
                json={"name": "Rent", "default_priority": "protected"},
            )
            category_id = created.json()["id"]
            updated = await client.patch(
                f"/api/categories/{category_id}",
                json={"default_priority": "essential"},
            )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert created.json()["default_priority"] == "protected"
    assert updated.status_code == 200
    assert updated.json()["default_priority"] == "essential"
    assert session.get(Category, category_id).default_priority is SpendingPriority.ESSENTIAL
