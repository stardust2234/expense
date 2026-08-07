import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.api.auth_dependencies import get_auth0_identity
from app.database.base import Base
from app.database.session import get_database_session
from app.main import app
from app.models import Category, User, Workspace
from app.services.auth0_service import Auth0Identity

pytestmark = pytest.mark.auth_boundary
current_identity = Auth0Identity("auth0|owner", "owner@example.com", "Owner")


@pytest.fixture
def session(tmp_path) -> Iterator[Session]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth.db'}", connect_args={"check_same_thread": False}
    )
    event.listen(
        engine, "connect", lambda connection, _record: connection.execute("PRAGMA foreign_keys=ON")
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as database_session:
        yield database_session


@pytest.fixture
async def client(session: Session) -> AsyncIterator[AsyncClient]:
    global current_identity
    current_identity = Auth0Identity("auth0|owner", "owner@example.com", "Owner")

    async def database_override() -> AsyncIterator[Session]:
        yield session

    async def identity_override() -> Auth0Identity:
        return current_identity

    app.dependency_overrides[get_database_session] = database_override
    app.dependency_overrides[get_auth0_identity] = identity_override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as value:
            yield value
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_auth0_config_is_public(client: AsyncClient) -> None:
    response = await client.get("/api/auth/config")
    assert response.status_code == 200
    assert set(response.json()) == {"domain", "client_id", "audience"}


@pytest.mark.anyio
async def test_bearer_token_is_required(client: AsyncClient) -> None:
    identity_override = app.dependency_overrides.pop(get_auth0_identity)
    try:
        assert (await client.get("/api/auth/me")).status_code == 401
    finally:
        app.dependency_overrides[get_auth0_identity] = identity_override


@pytest.mark.anyio
async def test_first_auth0_identity_claims_legacy_workspace(
    session: Session, client: AsyncClient
) -> None:
    workspace = Workspace(name="Existing", is_claimed=False)
    session.add(workspace)
    session.flush()
    session.add(Category(name="Existing category", workspace_id=workspace.id))
    session.commit()

    response = await asyncio.wait_for(
        client.get("/api/auth/me", headers={"Authorization": "Bearer valid"}), timeout=3
    )

    assert response.status_code == 200
    session.expire_all()
    owner = session.scalar(select(User).where(User.auth0_subject == "auth0|owner"))
    assert owner is not None and owner.workspace is workspace
    assert workspace.is_claimed is True


@pytest.mark.anyio
async def test_existing_email_is_linked_without_replacing_workspace(
    session: Session, client: AsyncClient
) -> None:
    user = User(email="owner@example.com", display_name="Legacy")
    workspace = Workspace(name="Personal", is_claimed=True, owner=user)
    session.add(workspace)
    session.commit()

    response = await asyncio.wait_for(
        client.get("/api/auth/me", headers={"Authorization": "Bearer valid"}), timeout=3
    )

    assert response.status_code == 200
    session.refresh(user)
    assert user.auth0_subject == "auth0|owner"
    assert user.workspace is workspace


@pytest.mark.anyio
async def test_auth0_identities_cannot_access_each_others_workspace_data(
    client: AsyncClient,
) -> None:
    global current_identity
    current_identity = Auth0Identity("auth0|first", "first@example.com", "First")
    first = await client.post(
        "/api/categories",
        headers={"Authorization": "Bearer first"},
        json={"name": "First private category", "default_priority": "optional"},
    )
    assert first.status_code == 201
    first_category_id = first.json()["id"]

    current_identity = Auth0Identity("auth0|second", "second@example.com", "Second")
    second_categories = await client.get(
        "/api/categories", headers={"Authorization": "Bearer second"}
    )
    assert second_categories.status_code == 200
    assert "First private category" not in {
        item["name"] for item in second_categories.json()["items"]
    }
    assert (
        await client.delete(
            f"/api/categories/{first_category_id}",
            headers={"Authorization": "Bearer second"},
        )
    ).status_code == 404

    current_identity = Auth0Identity("auth0|owner", "owner@example.com", "Owner")
