from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_database_session
from app.main import app
from app.models import AuthSession, Category, User, Workspace, WorkspaceMembership
from app.services.auth_service import register_user

pytestmark = pytest.mark.auth_boundary
BOOTSTRAP_TOKEN = "development-only-admin-bootstrap-secret"


def protected_headers(csrf_token: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": csrf_token,
        "X-Admin-Bootstrap-Token": BOOTSTRAP_TOKEN,
    }


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
        with Session(session.get_bind(), expire_on_commit=False) as request_session:
            yield request_session

    app.dependency_overrides[get_database_session] = override_database_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


async def csrf(client: AsyncClient) -> str:
    response = await client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


@pytest.mark.anyio
async def test_first_registration_atomically_claims_existing_workspace_and_data(
    session: Session,
    client: AsyncClient,
) -> None:
    workspace = Workspace(name="Existing personal workspace", is_claimed=False)
    session.add(workspace)
    session.flush()
    category = Category(name="Benefits", workspace_id=workspace.id)
    session.add(category)
    session.commit()

    token = await csrf(client)
    response = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": " Admin@Example.com ",
            "display_name": " First Admin ",
            "password": "a-long-test-password",
        },
    )

    assert response.status_code == 201
    session.expire_all()
    assert response.json()["user"] == {
        "id": 1,
        "email": "admin@example.com",
        "display_name": "First Admin",
        "is_admin": True,
        "workspace_id": workspace.id,
        "email_verified": False,
    }
    user = session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert "a-long-test-password" not in user.password_hash
    assert workspace.is_claimed is True
    assert category.workspace_id == workspace.id
    assert session.scalar(select(WorkspaceMembership)).role == "owner"
    stored_session = session.scalar(select(AuthSession))
    assert stored_session is not None
    assert stored_session.token_hash not in response.headers.get("set-cookie", "")
    assert "HttpOnly" in response.headers.get("set-cookie", "")
    session.commit()

    current = await client.get("/api/auth/session")
    assert current.status_code == 200
    assert current.json()["user"]["workspace_id"] == workspace.id


@pytest.mark.anyio
async def test_second_registration_gets_private_workspace_without_admin_role(
    session: Session,
    client: AsyncClient,
) -> None:
    first_workspace = Workspace(name="Legacy", is_claimed=False)
    session.add(first_workspace)
    session.commit()
    token = await csrf(client)
    await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "first@example.com",
            "display_name": "First",
            "password": "first-long-password",
        },
    )
    client.cookies.clear()
    token = await csrf(client)

    response = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "second@example.com",
            "display_name": "Second",
            "password": "second-long-password",
        },
    )

    assert response.status_code == 201
    assert response.json()["user"]["is_admin"] is False
    assert response.json()["user"]["workspace_id"] != first_workspace.id
    assert session.scalar(select(User).where(User.email == "first@example.com")).is_admin is True
    assert session.scalar(select(User).where(User.email == "second@example.com")).is_admin is False


@pytest.mark.anyio
async def test_login_logout_and_csrf_enforcement(session: Session, client: AsyncClient) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "user@example.com",
            "display_name": "User",
            "password": "correct-long-password",
        },
    )

    assert (await client.post("/api/auth/logout")).status_code == 403
    session_response = await client.get("/api/auth/session")
    current_csrf = await csrf(client)
    logout = await client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": current_csrf},
    )
    assert session_response.status_code == 200
    assert logout.status_code == 204
    assert (await client.get("/api/auth/session")).status_code == 401

    token = await csrf(client)
    bad_login = await client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401
    login = await client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"email": "user@example.com", "password": "correct-long-password"},
    )
    assert login.status_code == 200
    assert (await client.get("/api/auth/session")).status_code == 200


@pytest.mark.anyio
async def test_registration_requires_csrf_and_rejects_duplicate_email(
    session: Session,
    client: AsyncClient,
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    payload = {
        "email": "user@example.com",
        "display_name": "User",
        "password": "correct-long-password",
    }
    missing = await client.post("/api/auth/register", json=payload)
    assert missing.status_code == 403

    token = await csrf(client)
    assert (
        await client.post("/api/auth/register", headers=protected_headers(token), json=payload)
    ).status_code == 201
    client.cookies.clear()
    token = await csrf(client)
    duplicate = await client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json=payload,
    )
    assert duplicate.status_code == 409


@pytest.mark.anyio
async def test_account_can_change_email_and_must_verify_new_address(
    session: Session, client: AsyncClient
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "old@example.com",
            "display_name": "User",
            "password": "correct-long-password",
        },
    )
    token = await csrf(client)

    wrong = await client.patch(
        "/api/auth/account/email",
        headers={"X-CSRF-Token": token},
        json={"email": "new@example.com", "current_password": "wrong-password"},
    )
    changed = await client.patch(
        "/api/auth/account/email",
        headers={"X-CSRF-Token": token},
        json={"email": " New@Example.com ", "current_password": "correct-long-password"},
    )

    assert wrong.status_code == 400
    assert changed.status_code == 202
    assert changed.json()["development_token"]
    session.expire_all()
    user = session.scalar(select(User).where(User.email == "old@example.com"))
    assert user is not None
    assert user.pending_email == "new@example.com"
    verified = await client.post(
        "/api/auth/verify-email",
        json={"token": changed.json()["development_token"]},
    )
    assert verified.status_code == 204
    session.expire_all()
    user = session.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None
    assert user.pending_email is None
    assert user.email_verified_at is not None


@pytest.mark.anyio
async def test_account_deletion_removes_user_workspace_and_financial_data(
    session: Session, client: AsyncClient
) -> None:
    workspace = Workspace(name="Legacy", is_claimed=False)
    session.add(workspace)
    session.flush()
    session.add(Category(name="Test data", workspace_id=workspace.id))
    session.commit()
    token = await csrf(client)
    created = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "delete@example.com",
            "display_name": "Delete Me",
            "password": "correct-long-password",
        },
    )
    user_id = created.json()["user"]["id"]
    workspace_id = created.json()["user"]["workspace_id"]
    token = await csrf(client)

    wrong = await client.request(
        "DELETE",
        "/api/auth/account",
        headers={"X-CSRF-Token": token},
        json={"current_password": "wrong-password", "confirmation": "DELETE"},
    )
    deleted = await client.request(
        "DELETE",
        "/api/auth/account",
        headers={"X-CSRF-Token": token},
        json={"current_password": "correct-long-password", "confirmation": "DELETE"},
    )

    assert wrong.status_code == 400
    assert deleted.status_code == 204
    session.expire_all()
    assert session.get(User, user_id) is None
    assert session.get(Workspace, workspace_id) is None
    assert session.scalar(select(Category).where(Category.name == "Test data")) is None
    assert (await client.get("/api/auth/session")).status_code == 401


@pytest.mark.anyio
async def test_administrator_can_manage_workspace_users_and_read_audit(
    session: Session, client: AsyncClient
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    registration = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "admin@example.com",
            "display_name": "Administrator",
            "password": "administrator-password",
        },
    )
    user_id = registration.json()["user"]["id"]
    token = await csrf(client)

    users = await client.get("/api/auth/admin/users")
    self_demotion = await client.patch(
        f"/api/auth/admin/users/{user_id}",
        headers={"X-CSRF-Token": token},
        json={"is_admin": False},
    )
    audit_response = await client.get("/api/auth/admin/audit")

    assert users.status_code == 200
    assert users.json()[0]["email"] == "admin@example.com"
    assert self_demotion.status_code == 409
    assert audit_response.status_code == 200


@pytest.mark.anyio
async def test_first_administrator_requires_the_one_time_bootstrap_token(
    session: Session,
    client: AsyncClient,
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    assert (await client.get("/api/auth/bootstrap-status")).json() == {"required": True}
    token = await csrf(client)
    payload = {
        "email": "admin@example.com",
        "display_name": "Admin",
        "password": "administrator-password",
    }

    missing = await client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token},
        json=payload,
    )
    wrong = await client.post(
        "/api/auth/register",
        headers={"X-CSRF-Token": token, "X-Admin-Bootstrap-Token": "wrong"},
        json=payload,
    )
    created = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json=payload,
    )

    assert missing.status_code == 403
    assert wrong.status_code == 403
    assert created.status_code == 201
    assert created.json()["user"]["is_admin"] is True
    assert (await client.get("/api/auth/bootstrap-status")).json() == {"required": False}


def test_concurrent_initial_registrations_elect_exactly_one_administrator(
    tmp_path: Path,
) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as setup_session:
        setup_session.add(Workspace(name="Legacy", is_claimed=False))
        setup_session.commit()

    def create(email: str) -> int:
        with Session(engine, expire_on_commit=False) as database_session:
            return register_user(
                database_session,
                email=email,
                display_name=email.split("@", maxsplit=1)[0],
                password="concurrent-long-password",
                session_days=7,
                bootstrap_secret=BOOTSTRAP_TOKEN,
                supplied_bootstrap_token=BOOTSTRAP_TOKEN,
            ).user.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        user_ids = list(executor.map(create, ["one@example.com", "two@example.com"]))

    with Session(engine) as verification_session:
        users = verification_session.scalars(select(User).where(User.id.in_(user_ids))).all()
        workspaces = verification_session.scalars(select(Workspace)).all()
        memberships = verification_session.scalars(
            select(WorkspaceMembership).where(WorkspaceMembership.user_id.in_(user_ids))
        ).all()
    assert sum(user.is_admin for user in users) == 1
    assert len({membership.workspace_id for membership in memberships}) == 2
    assert sum(workspace.is_claimed for workspace in workspaces) == 2


@pytest.mark.anyio
async def test_users_cannot_list_or_mutate_another_workspace_categories(
    session: Session,
    client: AsyncClient,
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    first_csrf = await csrf(client)
    first_registration = await client.post(
        "/api/auth/register",
        headers=protected_headers(first_csrf),
        json={
            "email": "owner@example.com",
            "display_name": "Owner",
            "password": "owner-long-password",
        },
    )
    first_csrf = first_registration.json()["csrf_token"]
    owner = session.scalar(select(User).where(User.email == "owner@example.com"))
    owner.email_verified_at = datetime.now(UTC)
    session.commit()
    created = await client.post(
        "/api/categories",
        headers={"X-CSRF-Token": first_csrf},
        json={"name": "Private category"},
    )
    assert created.status_code == 201
    category_id = created.json()["id"]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as other_client:
        other_csrf = await csrf(other_client)
        registration = await other_client.post(
            "/api/auth/register",
            headers=protected_headers(other_csrf),
            json={
                "email": "other@example.com",
                "display_name": "Other",
                "password": "other-long-password",
            },
        )
        other_csrf = registration.json()["csrf_token"]
        other = session.scalar(select(User).where(User.email == "other@example.com"))
        other.email_verified_at = datetime.now(UTC)
        session.commit()
        other_categories = (await other_client.get("/api/categories")).json()["items"]
        assert "Private category" not in {item["name"] for item in other_categories}
        attempted_update = await other_client.patch(
            f"/api/categories/{category_id}",
            headers={"X-CSRF-Token": other_csrf},
            json={"name": "Stolen"},
        )
        assert attempted_update.status_code == 404

    first_categories = await client.get("/api/categories")
    assert "Private category" in {item["name"] for item in first_categories.json()["items"]}


@pytest.mark.anyio
async def test_expired_session_is_rejected(session: Session, client: AsyncClient) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "expired@example.com",
            "display_name": "Expired",
            "password": "expired-long-password",
        },
    )
    stored = session.scalar(select(AuthSession))
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()

    assert (await client.get("/api/auth/session")).status_code == 401


@pytest.mark.anyio
async def test_login_rotates_and_revokes_existing_session(
    session: Session,
    client: AsyncClient,
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "rotate@example.com",
            "display_name": "Rotate",
            "password": "rotate-long-password",
        },
    )
    original_cookie = client.cookies.get("expense_session")
    token = await csrf(client)
    login = await client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"email": "rotate@example.com", "password": "rotate-long-password"},
    )
    assert login.status_code == 200
    assert client.cookies.get("expense_session") != original_cookie
    session.expire_all()
    sessions = session.scalars(select(AuthSession).order_by(AuthSession.id)).all()
    assert sessions[0].revoked_at is not None
    assert sessions[1].revoked_at is None


@pytest.mark.anyio
async def test_login_is_throttled_after_repeated_failures(
    session: Session,
    client: AsyncClient,
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": token},
            json={"email": "missing@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
    blocked = await client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
