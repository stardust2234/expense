from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from argon2.exceptions import VerifyMismatchError
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import AccountToken, AuditEvent, AuthSession, User
from app.services.auth_service import _password_hasher


class AccountTokenError(ValueError):
    pass


class PasswordError(ValueError):
    pass


def issue_token(session: Session, *, user: User, purpose: str, minutes: int) -> str:
    now = datetime.now(UTC)
    session.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user.id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw = token_urlsafe(32)
    session.add(
        AccountToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=sha256(raw.encode()).hexdigest(),
            expires_at=now + timedelta(minutes=minutes),
        )
    )
    return raw


def consume_token(session: Session, *, raw: str, purpose: str) -> User:
    now = datetime.now(UTC)
    user_id = session.scalar(
        update(AccountToken)
        .where(
            AccountToken.token_hash == sha256(raw.encode()).hexdigest(),
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(AccountToken.user_id)
    )
    if user_id is None:
        raise AccountTokenError("Token is invalid or expired")
    user = session.get(User, user_id)
    if user is None:
        raise AccountTokenError("Token is invalid or expired")
    return user


def change_password(
    session: Session,
    *,
    user: User,
    current: str,
    new: str,
    current_session_id: int,
) -> None:
    if not verify_password(user, current):
        raise PasswordError("Current password is incorrect")
    user.password_hash = _password_hasher.hash(new)
    revoke_user_sessions(session, user.id, except_id=current_session_id)


def verify_password(user: User, password: str) -> bool:
    try:
        return _password_hasher.verify(user.password_hash, password)
    except VerifyMismatchError:
        return False


def reset_password(session: Session, *, token: str, new: str) -> User:
    user = consume_token(session, raw=token, purpose="password_reset")
    user.password_hash = _password_hasher.hash(new)
    revoke_user_sessions(session, user.id)
    return user


def revoke_user_sessions(session: Session, user_id: int, *, except_id: int | None = None) -> None:
    statement = update(AuthSession).where(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
    )
    if except_id is not None:
        statement = statement.where(AuthSession.id != except_id)
    session.execute(statement.values(revoked_at=datetime.now(UTC)))


def audit(
    session: Session,
    *,
    event_type: str,
    workspace_id: int | None,
    actor_user_id: int | None,
    target_user_id: int | None = None,
    client_ip: str | None = None,
    details: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            event_type=event_type,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            client_ip=client_ip,
            details=details or {},
        )
    )
