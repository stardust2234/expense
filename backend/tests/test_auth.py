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
from app.models import AccountToken, AuditEvent, AuthSession, Category, User, Workspace
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
    response_user = response.json()["user"]
    assert response_user == {
        "id": 1,
        "email": "admin@example.com",
        "display_name": "First Admin",
        "workspace_id": workspace.id,
        "email_verified": False,
        "trial_ends_at": response_user["trial_ends_at"],
        "access_expires_at": None,
        "access_active": True,
    }
    user = session.scalar(select(User).where(User.email == "admin@example.com"))
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert "a-long-test-password" not in user.password_hash
    assert workspace.is_claimed is True
    assert category.workspace_id == workspace.id
    assert workspace.owner_user_id == user.id
    assert user.workspace is workspace
    stored_session = session.scalar(select(AuthSession))
    assert stored_session is not None
    assert stored_session.token_hash not in response.headers.get("set-cookie", "")
    assert "HttpOnly" in response.headers.get("set-cookie", "")
    session.commit()

    current = await client.get("/api/auth/session")
    assert current.status_code == 200
    assert current.json()["user"]["workspace_id"] == workspace.id


@pytest.mark.anyio
async def test_second_registration_is_owner_of_its_private_workspace(
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
    assert response.json()["user"]["workspace_id"] != first_workspace.id
    first = session.scalar(select(User).where(User.email == "first@example.com"))
    second = session.scalar(select(User).where(User.email == "second@example.com"))
    assert first is not None and first.workspace is first_workspace
    assert second is not None and second.workspace is not None
    assert second.workspace.owner_user_id == second.id


@pytest.mark.anyio
async def test_expired_trial_blocks_financial_api_but_keeps_account_session_available(
    session: Session,
    client: AsyncClient,
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    registration = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "expired-trial@example.com",
            "display_name": "Expired Trial",
            "password": "a-long-test-password",
        },
    )
    assert registration.status_code == 201
    workspace_id = registration.json()["user"]["workspace_id"]
    user = session.scalar(select(User).where(User.email == "expired-trial@example.com"))
    assert user is not None
    user.email_verified_at = datetime.now(UTC)
    workspace = session.get(Workspace, workspace_id)
    assert workspace is not None
    workspace.trial_ends_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()

    financial = await client.get("/api/categories")
    assert financial.status_code == 402
    assert financial.json()["detail"] == "Your free trial has expired"

    current = await client.get("/api/auth/session")
    assert current.status_code == 200
    assert current.json()["user"]["access_active"] is False


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
async def test_csrf_endpoint_reuses_a_valid_authenticated_token_across_tabs(
    session: Session, client: AsyncClient
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    public_token = await csrf(client)
    registration = await client.post(
        "/api/auth/register",
        headers=protected_headers(public_token),
        json={
            "email": "csrf@example.com",
            "display_name": "CSRF User",
            "password": "correct-long-password",
        },
    )
    issued_token = registration.json()["csrf_token"]

    first_tab_token = await csrf(client)
    second_tab_token = await csrf(client)

    assert first_tab_token == issued_token
    assert second_tab_token == issued_token
    assert (
        await client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": first_tab_token},
        )
    ).status_code == 204


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
    assert session.scalar(select(AuthSession).where(AuthSession.user_id == user_id)) is None
    assert session.scalar(select(AccountToken).where(AccountToken.user_id == user_id)) is None
    assert (await client.get("/api/auth/session")).status_code == 401


@pytest.mark.anyio
async def test_password_change_preserves_current_session_and_revokes_other_sessions(
    session: Session, client: AsyncClient
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    registration = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "password-change@example.com",
            "display_name": "Password Change",
            "password": "correct-long-password",
        },
    )
    current_session_id = session.scalar(
        select(AuthSession.id).where(AuthSession.user_id == registration.json()["user"]["id"])
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as other_client:
        other_csrf = await csrf(other_client)
        other_login = await other_client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": other_csrf},
            json={
                "email": "password-change@example.com",
                "password": "correct-long-password",
            },
        )
        assert other_login.status_code == 200
        changed = await client.post(
            "/api/auth/password/change",
            headers={"X-CSRF-Token": registration.json()["csrf_token"]},
            json={
                "current_password": "correct-long-password",
                "new_password": "replacement-long-password",
            },
        )

        assert changed.status_code == 204
        assert (await client.get("/api/auth/session")).status_code == 200
        assert (await other_client.get("/api/auth/session")).status_code == 401

    session.expire_all()
    sessions = session.scalars(
        select(AuthSession).where(AuthSession.user_id == registration.json()["user"]["id"])
    ).all()
    assert next(item for item in sessions if item.id == current_session_id).revoked_at is None
    assert all(item.revoked_at is not None for item in sessions if item.id != current_session_id)


@pytest.mark.anyio
async def test_owner_can_read_audit_and_workspace_user_management_is_absent(
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
    token = await csrf(client)

    users = await client.get("/api/auth/admin/users")
    role_update = await client.patch(
        f"/api/auth/admin/users/{registration.json()['user']['id']}",
        headers={"X-CSRF-Token": token},
        json={"is_admin": False},
    )
    audit_response = await client.get("/api/auth/account/audit")

    assert users.status_code == 404
    assert role_update.status_code == 404
    assert audit_response.status_code == 200


@pytest.mark.anyio
async def test_owner_can_probe_and_test_email_delivery(
    session: Session,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    registration = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "mail-admin@example.com",
            "display_name": "Mail Admin",
            "password": "mail-admin-long-password",
        },
    )
    token = registration.json()["csrf_token"]
    calls: list[str] = []
    monkeypatch.setattr(
        "app.api.routes.email_diagnostics.check_smtp_readiness",
        lambda _settings: calls.append("readiness"),
    )
    monkeypatch.setattr(
        "app.api.routes.email_diagnostics.send_delivery_test",
        lambda _settings, *, email: calls.append(f"delivery:{email}"),
    )

    readiness = await client.get("/api/auth/account/email-delivery/readiness")
    delivery = await client.post(
        "/api/auth/account/email-delivery/test",
        headers={"X-CSRF-Token": token},
    )

    assert readiness.status_code == 200
    assert readiness.json() == {"status": "ready"}
    assert delivery.status_code == 202
    assert delivery.json() == {"status": "accepted"}
    assert calls == ["readiness", "delivery:mail-admin@example.com"]
    session.expire_all()
    assert session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "account.email_delivery_tested")
    )


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
    assert (await client.get("/api/auth/bootstrap-status")).json() == {"required": False}


def test_concurrent_initial_registrations_create_one_workspace_per_owner(
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
            issued = register_user(
                database_session,
                email=email,
                display_name=email.split("@", maxsplit=1)[0],
                password="concurrent-long-password",
                session_days=7,
                bootstrap_secret=BOOTSTRAP_TOKEN,
                supplied_bootstrap_token=BOOTSTRAP_TOKEN,
            )
            database_session.commit()
            return issued.user.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        user_ids = list(executor.map(create, ["one@example.com", "two@example.com"]))

    with Session(engine) as verification_session:
        workspaces = verification_session.scalars(select(Workspace)).all()
    assert {workspace.owner_user_id for workspace in workspaces} == set(user_ids)
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


@pytest.mark.anyio
async def test_login_aggregate_ip_throttle_blocks_identity_rotation(client: AsyncClient) -> None:
    token = await csrf(client)
    attempts = [
        await client.post(
            "/api/auth/login",
            headers={"X-CSRF-Token": token},
            json={"email": f"missing-{index}@example.com", "password": "wrong-password"},
        )
        for index in range(20)
    ]
    blocked = await client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": token},
        json={"email": "another-missing@example.com", "password": "wrong-password"},
    )

    assert all(response.status_code == 401 for response in attempts)
    assert blocked.status_code == 429


@pytest.mark.anyio
async def test_verification_resend_and_password_reset_are_throttled(
    session: Session,
    client: AsyncClient,
) -> None:
    session.add(Workspace(name="Legacy", is_claimed=False))
    session.commit()
    token = await csrf(client)
    registration = await client.post(
        "/api/auth/register",
        headers=protected_headers(token),
        json={
            "email": "email-throttle@example.com",
            "display_name": "Email Throttle",
            "password": "email-throttle-password",
        },
    )
    token = registration.json()["csrf_token"]

    resend = [
        await client.post(
            "/api/auth/verification/resend",
            headers={"X-CSRF-Token": token},
        )
        for _ in range(4)
    ]
    reset = [
        await client.post(
            "/api/auth/password-reset/request",
            json={"email": "missing@example.com"},
        )
        for _ in range(4)
    ]

    assert [response.status_code for response in resend] == [202, 202, 202, 429]
    assert [response.status_code for response in reset] == [202, 202, 202, 429]


@pytest.mark.anyio
async def test_email_aggregate_ip_throttle_blocks_identity_rotation(client: AsyncClient) -> None:
    attempts = [
        await client.post(
            "/api/auth/password-reset/request",
            json={"email": f"missing-{index}@example.com"},
        )
        for index in range(20)
    ]

    assert [response.status_code for response in attempts[:19]] == [202] * 19
    assert attempts[19].status_code == 429
