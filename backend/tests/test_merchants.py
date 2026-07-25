from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_database_session
from app.main import app
from app.models import Merchant, MerchantAlias
from app.services.matching import MerchantCandidate, identify_merchant


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
async def test_merchant_and_alias_management(session: Session) -> None:
    async def override_database_session() -> AsyncIterator[Session]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            create_response = await client.post(
                "/api/merchants",
                json={"name": "Tesco", "aliases": ["TESCO STORES"]},
            )
            merchant_id = create_response.json()["id"]
            alias_response = await client.post(
                f"/api/merchants/{merchant_id}/aliases",
                json={"pattern": "TESCO EXPRESS"},
            )
            list_response = await client.get("/api/merchants")
            delete_response = await client.delete(
                f"/api/merchants/{merchant_id}/aliases/{alias_response.json()['id']}"
            )
    finally:
        app.dependency_overrides.clear()

    assert create_response.status_code == 201
    assert alias_response.status_code == 201
    assert list_response.status_code == 200
    assert [alias["pattern"] for alias in list_response.json()["items"][0]["aliases"]] == [
        "TESCO EXPRESS",
        "TESCO STORES",
    ]
    assert delete_response.status_code == 204
    assert len(session.scalars(select(MerchantAlias)).all()) == 1


@pytest.mark.anyio
async def test_duplicate_alias_returns_conflict(session: Session) -> None:
    first = Merchant(name="First", aliases=[MerchantAlias(pattern="CARD PAYMENT SHOP")])
    second = Merchant(name="Second")
    session.add_all([first, second])
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
                f"/api/merchants/{second.id}/aliases",
                json={"pattern": "card payment shop"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


@pytest.mark.anyio
async def test_merchants_can_be_merged(session: Session) -> None:
    target = Merchant(name="Amazon", aliases=[MerchantAlias(pattern="AMAZON")])
    source = Merchant(name="Amazon EU", aliases=[MerchantAlias(pattern="AMZN MKTP")])
    session.add_all([target, source])
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
                f"/api/merchants/{target.id}/merge",
                json={"source_merchant_id": source.id},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert {alias["pattern"] for alias in response.json()["aliases"]} == {
        "AMAZON",
        "AMZN MKTP",
    }
    assert session.get(Merchant, source.id) is None


def test_merchant_alias_participates_in_identification() -> None:
    match = identify_merchant(
        "TESCO STORES 0123 LONDON",
        [
            MerchantCandidate(
                id=42,
                name="Tesco",
                aliases=("TESCO STORES",),
            )
        ],
    )

    assert match is not None
    assert match.merchant_id == 42
