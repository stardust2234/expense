from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new
from secrets import token_urlsafe

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import case, func, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import (
    AuthActionThrottle,
    AuthSession,
    LoginThrottle,
    User,
    Workspace,
)
from app.services.category_seed_service import seed_categories

SESSION_COOKIE = "expense_session"
CSRF_COOKIE = "expense_csrf"
CSRF_HEADER = "X-CSRF-Token"
_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
_dummy_hash = _password_hasher.hash("not-a-real-user-password")


class AuthenticationError(ValueError):
    pass


class RegistrationConflictError(ValueError):
    pass


class LoginThrottledError(ValueError):
    pass


class BootstrapProtectionError(ValueError):
    pass


@dataclass(frozen=True)
class IssuedSession:
    user: User
    workspace_id: int
    raw_token: str
    csrf_token: str
    expires_at: datetime


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def workspace_access_ends_at(workspace: Workspace) -> datetime:
    trial_end = _aware(workspace.trial_ends_at)
    if workspace.access_expires_at is None:
        return trial_end
    return max(trial_end, _aware(workspace.access_expires_at))


def workspace_access_active(workspace: Workspace, *, now: datetime | None = None) -> bool:
    return workspace_access_ends_at(workspace) > (now or datetime.now(UTC))


def register_user(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    session_days: int,
    bootstrap_secret: str | None = None,
    supplied_bootstrap_token: str | None = None,
) -> IssuedSession:
    if session.get_bind().dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))
    try:
        if session.scalar(select(User.id).where(User.email == email)) is not None:
            raise RegistrationConflictError("An account with this email already exists")

        first_user = (session.scalar(select(func.count()).select_from(User)) or 0) == 0
        if first_user and (
            not bootstrap_secret
            or not supplied_bootstrap_token
            or not compare_digest(bootstrap_secret, supplied_bootstrap_token)
        ):
            raise BootstrapProtectionError(
                "A valid one-time administrator bootstrap token is required"
            )
        user = User(
            email=email,
            display_name=display_name,
            password_hash=_password_hasher.hash(password),
        )
        session.add(user)
        session.flush()

        workspace = None
        if first_user:
            workspace = session.scalar(
                select(Workspace)
                .where(Workspace.is_claimed.is_(False))
                .order_by(Workspace.id)
                .limit(1)
            )
        if workspace is None:
            workspace = Workspace(name=f"{display_name}'s workspace", is_claimed=True, owner=user)
            session.add(workspace)
            session.flush()
        else:
            workspace.is_claimed = True
            workspace.name = f"{display_name}'s workspace"
            workspace.owner = user

        session.info["workspace_id"] = workspace.id
        seed_categories(session, commit=False)
        issued = _create_session(
            session, user=user, workspace_id=workspace.id, session_days=session_days
        )
        return issued
    except IntegrityError as error:
        raise RegistrationConflictError("An account with this email already exists") from error


def administrator_bootstrap_required(session: Session) -> bool:
    return (session.scalar(select(func.count()).select_from(User)) or 0) == 0


def login_user(
    session: Session,
    *,
    email: str,
    password: str,
    session_days: int,
    identity_throttle_key: str,
    ip_throttle_key: str,
    existing_token: str | None = None,
) -> IssuedSession:
    _check_login_throttle(session, identity_throttle_key)
    _check_login_throttle(session, ip_throttle_key)
    user = session.scalar(
        select(User).where(User.email == email).options(selectinload(User.workspace))
    )
    candidate_hash = user.password_hash if user is not None else _dummy_hash
    try:
        valid = _password_hasher.verify(candidate_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        valid = False
    if user is None or not valid or user.workspace is None:
        _record_login_failure(session, identity_throttle_key, limit=5)
        _record_login_failure(session, ip_throttle_key, limit=20)
        raise AuthenticationError("Invalid email or password")
    if _password_hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _password_hasher.hash(password)
    _clear_login_failures(session, identity_throttle_key)
    if existing_token:
        existing = session.scalar(
            select(AuthSession).where(AuthSession.token_hash == _hash_token(existing_token))
        )
        if existing is not None and existing.revoked_at is None:
            existing.revoked_at = datetime.now(UTC)
    issued = _create_session(
        session,
        user=user,
        workspace_id=user.workspace.id,
        session_days=session_days,
    )
    return issued


def _create_session(
    session: Session, *, user: User, workspace_id: int, session_days: int
) -> IssuedSession:
    raw_token = token_urlsafe(32)
    csrf_token = token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=session_days)
    session.add(
        AuthSession(
            user=user,
            token_hash=_hash_token(raw_token),
            csrf_token_hash=_hash_token(csrf_token),
            expires_at=expires_at,
        )
    )
    return IssuedSession(user, workspace_id, raw_token, csrf_token, expires_at)


def get_auth_session(session: Session, raw_token: str | None) -> tuple[AuthSession, int] | None:
    if not raw_token:
        return None
    auth_session = session.scalar(
        select(AuthSession)
        .where(AuthSession.token_hash == _hash_token(raw_token))
        .options(selectinload(AuthSession.user).selectinload(User.workspace))
    )
    now = datetime.now(UTC)
    if auth_session is None or auth_session.revoked_at is not None:
        return None
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now or auth_session.user.workspace is None:
        return None
    auth_session.last_used_at = now
    return auth_session, auth_session.user.workspace.id


def verify_csrf(auth_session: AuthSession, supplied_token: str | None) -> bool:
    return bool(
        supplied_token and compare_digest(auth_session.csrf_token_hash, _hash_token(supplied_token))
    )


def rotate_csrf(auth_session: AuthSession) -> str:
    token = token_urlsafe(32)
    auth_session.csrf_token_hash = _hash_token(token)
    return token


def revoke_session(session: Session, auth_session: AuthSession) -> None:
    auth_session.revoked_at = datetime.now(UTC)


def login_throttle_keys(*, email: str, client_ip: str, secret: str) -> tuple[str, str]:
    identity = f"login-identity\0{email.strip().casefold()}\0{client_ip}".encode()
    aggregate_ip = f"login-ip\0{client_ip}".encode()
    return (
        hmac_new(secret.encode(), identity, sha256).hexdigest(),
        hmac_new(secret.encode(), aggregate_ip, sha256).hexdigest(),
    )


def enforce_registration_throttle(session: Session, *, client_ip: str, secret: str) -> None:
    key = hmac_new(secret.encode(), f"registration\0{client_ip}".encode(), sha256).hexdigest()
    _enforce_action_throttle(
        session,
        key=key,
        limit=5,
        window=timedelta(hours=1),
        message="Too many registration attempts; try again later",
    )


def enforce_email_throttle(
    session: Session,
    *,
    action: str,
    identity: str,
    client_ip: str,
    secret: str,
) -> None:
    aggregate_material = f"email-ip\0{client_ip}".encode()
    aggregate_key = hmac_new(secret.encode(), aggregate_material, sha256).hexdigest()
    _enforce_action_throttle(
        session,
        key=aggregate_key,
        limit=20,
        window=timedelta(hours=1),
        message="Too many email requests; try again later",
    )
    identity_material = f"{action}\0{identity.strip().casefold()}\0{client_ip}".encode()
    identity_key = hmac_new(secret.encode(), identity_material, sha256).hexdigest()
    _enforce_action_throttle(
        session,
        key=identity_key,
        limit=4,
        window=timedelta(hours=1),
        message="Too many email requests; try again later",
    )


def _enforce_action_throttle(
    session: Session,
    *,
    key: str,
    limit: int,
    window: timedelta,
    message: str,
) -> None:
    now = datetime.now(UTC)
    window_start = now - window
    blocked_until = now + window
    statement = sqlite_insert(AuthActionThrottle).values(
        key_hash=key, attempts=1, window_started_at=now, blocked_until=None
    )
    statement = statement.on_conflict_do_update(
        index_elements=[AuthActionThrottle.key_hash],
        set_={
            "attempts": case(
                (AuthActionThrottle.window_started_at <= window_start, 1),
                else_=AuthActionThrottle.attempts + 1,
            ),
            "window_started_at": case(
                (AuthActionThrottle.window_started_at <= window_start, now),
                else_=AuthActionThrottle.window_started_at,
            ),
            "blocked_until": case(
                (AuthActionThrottle.window_started_at <= window_start, None),
                (AuthActionThrottle.attempts + 1 >= limit, blocked_until),
                else_=AuthActionThrottle.blocked_until,
            ),
        },
    ).returning(AuthActionThrottle.attempts, AuthActionThrottle.blocked_until)
    attempts, blocked = session.execute(statement).one()
    if attempts >= limit or (blocked is not None and _aware(blocked) > now):
        raise LoginThrottledError(message)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _check_login_throttle(session: Session, key_hash: str) -> None:
    throttle = session.scalar(select(LoginThrottle).where(LoginThrottle.key_hash == key_hash))
    if (
        throttle is not None
        and throttle.blocked_until is not None
        and _aware(throttle.blocked_until) > datetime.now(UTC)
    ):
        raise LoginThrottledError("Too many login attempts; try again later")


def _record_login_failure(session: Session, key_hash: str, *, limit: int) -> None:
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=15)
    blocked_until = now + timedelta(minutes=15)
    statement = sqlite_insert(LoginThrottle).values(
        key_hash=key_hash, failed_attempts=1, window_started_at=now, blocked_until=None
    )
    statement = statement.on_conflict_do_update(
        index_elements=[LoginThrottle.key_hash],
        set_={
            "failed_attempts": case(
                (LoginThrottle.window_started_at <= window_start, 1),
                else_=LoginThrottle.failed_attempts + 1,
            ),
            "window_started_at": case(
                (LoginThrottle.window_started_at <= window_start, now),
                else_=LoginThrottle.window_started_at,
            ),
            "blocked_until": case(
                (LoginThrottle.window_started_at <= window_start, None),
                (LoginThrottle.failed_attempts + 1 >= limit, blocked_until),
                else_=LoginThrottle.blocked_until,
            ),
        },
    )
    session.execute(statement)


def _clear_login_failures(session: Session, key_hash: str) -> None:
    throttle = session.scalar(select(LoginThrottle).where(LoginThrottle.key_hash == key_hash))
    if throttle is not None:
        session.delete(throttle)
