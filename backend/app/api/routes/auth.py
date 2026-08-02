import logging
from datetime import UTC, datetime
from hmac import compare_digest
from secrets import token_urlsafe

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.auth_dependencies import CsrfProtectedAuth, CurrentAuth, DatabaseSession
from app.config import get_settings
from app.models import AuditEvent, AuthSession, User, Workspace
from app.schemas.auth import (
    AccountDeletionRequest,
    AuthenticatedUser,
    AuthSessionResponse,
    BootstrapStatusResponse,
    CsrfResponse,
    EmailChangeRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmation,
    RegistrationRequest,
    SessionItem,
    TokenConfirmation,
    TokenRequest,
    UserAdminItem,
    UserAdminUpdate,
)
from app.services.account_security_service import (
    AccountTokenError,
    PasswordError,
    audit,
    change_password,
    consume_token,
    issue_token,
    reset_password,
    revoke_user_sessions,
    verify_password,
    workspace_users,
)
from app.services.auth_service import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AuthenticationError,
    BootstrapProtectionError,
    IssuedSession,
    LoginThrottledError,
    RegistrationConflictError,
    administrator_bootstrap_required,
    enforce_registration_throttle,
    get_auth_session,
    login_throttle_key,
    login_user,
    register_user,
    revoke_session,
    rotate_csrf,
    workspace_access_active,
)
from app.services.mail_service import send_account_token

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()
logger = logging.getLogger(__name__)


def _set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_days * 24 * 60 * 60,
    )


def _set_session_cookies(response: Response, issued: IssuedSession) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        issued.raw_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_days * 24 * 60 * 60,
    )
    _set_csrf_cookie(response, issued.csrf_token)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=settings.auth_cookie_secure, samesite="lax"
    )
    response.delete_cookie(
        CSRF_COOKIE, path="/", secure=settings.auth_cookie_secure, samesite="lax"
    )


def _user_response(issued: IssuedSession, *, include_csrf: bool = True) -> AuthSessionResponse:
    workspace = next(
        membership.workspace
        for membership in issued.user.memberships
        if membership.workspace_id == issued.workspace_id
    )
    return AuthSessionResponse(
        user=AuthenticatedUser(
            id=issued.user.id,
            email=issued.user.email,
            display_name=issued.user.display_name,
            is_admin=issued.user.is_admin,
            workspace_id=issued.workspace_id,
            email_verified=issued.user.email_verified_at is not None,
            trial_ends_at=workspace.trial_ends_at,
            access_expires_at=workspace.access_expires_at,
            access_active=workspace_access_active(workspace),
        ),
        expires_at=issued.expires_at,
        csrf_token=issued.csrf_token if include_csrf else None,
    )


def _require_bootstrap_csrf(
    request: Request,
    csrf_token: str | None,
) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    if not csrf_token or not cookie_token or not compare_digest(csrf_token, cookie_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


@router.get("/csrf", response_model=CsrfResponse)
async def get_csrf(response: Response, session: DatabaseSession, request: Request) -> CsrfResponse:
    existing = get_auth_session(session, request.cookies.get(SESSION_COOKIE))
    token = rotate_csrf(session, existing[0]) if existing is not None else token_urlsafe(32)
    _set_csrf_cookie(response, token)
    return CsrfResponse(csrf_token=token)


@router.post(
    "/register",
    response_model=AuthSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegistrationRequest,
    response: Response,
    request: Request,
    session: DatabaseSession,
    x_csrf_token: str | None = Header(default=None),
    x_admin_bootstrap_token: str | None = Header(default=None),
) -> AuthSessionResponse:
    if not settings.allow_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Registration is disabled"
        )
    _require_bootstrap_csrf(request, x_csrf_token)
    try:
        enforce_registration_throttle(
            session,
            client_ip=request.client.host if request.client else "unknown",
            secret=settings.auth_throttle_secret,
        )
        issued = register_user(
            session,
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
            session_days=settings.session_days,
            bootstrap_secret=settings.admin_bootstrap_secret,
            supplied_bootstrap_token=x_admin_bootstrap_token,
        )
    except BootstrapProtectionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except RegistrationConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    _set_session_cookies(response, issued)
    raw = issue_token(session, user=issued.user, purpose="email_verification", minutes=60)
    try:
        send_account_token(
            settings, email=issued.user.email, purpose="email_verification", token=raw
        )
    except Exception:
        logger.exception("Could not send verification email")
    return _user_response(issued)


@router.get("/bootstrap-status", response_model=BootstrapStatusResponse)
async def bootstrap_status(session: DatabaseSession) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(required=administrator_bootstrap_required(session))


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    session: DatabaseSession,
    x_csrf_token: str | None = Header(default=None),
) -> AuthSessionResponse:
    _require_bootstrap_csrf(request, x_csrf_token)
    try:
        throttle_key = login_throttle_key(
            email=payload.email,
            client_ip=request.client.host if request.client else "unknown",
            secret=settings.auth_throttle_secret,
        )
        issued = login_user(
            session,
            email=payload.email,
            password=payload.password,
            session_days=settings.session_days,
            throttle_key=throttle_key,
            existing_token=request.cookies.get(SESSION_COOKIE),
        )
    except LoginThrottledError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(error)
        ) from error
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    _set_session_cookies(response, issued)
    audit(
        session,
        event_type="account.login",
        workspace_id=issued.workspace_id,
        actor_user_id=issued.user.id,
    )
    session.commit()
    return _user_response(issued)


@router.get("/session", response_model=AuthSessionResponse)
async def current_session(auth: CurrentAuth) -> AuthSessionResponse:
    workspace = next(
        membership.workspace
        for membership in auth.user.memberships
        if membership.workspace_id == auth.workspace_id
    )
    return AuthSessionResponse(
        user=AuthenticatedUser(
            id=auth.user.id,
            email=auth.user.email,
            display_name=auth.user.display_name,
            is_admin=auth.user.is_admin,
            workspace_id=auth.workspace_id,
            email_verified=auth.user.email_verified_at is not None,
            trial_ends_at=workspace.trial_ends_at,
            access_expires_at=workspace.access_expires_at,
            access_active=workspace_access_active(workspace),
        ),
        expires_at=auth.session.expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    auth: CsrfProtectedAuth,
    session: DatabaseSession,
) -> None:
    audit(
        session,
        event_type="account.logout",
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user.id,
    )
    revoke_session(session, auth.session)
    _clear_auth_cookies(response)


@router.post("/verify-email", status_code=204)
async def verify_email(payload: TokenConfirmation, session: DatabaseSession) -> None:
    try:
        try:
            user = consume_token(session, raw=payload.token, purpose="email_change")
            if not user.pending_email:
                raise AccountTokenError("Token is invalid or expired")
            user.email = user.pending_email
            user.pending_email = None
        except AccountTokenError:
            user = consume_token(session, raw=payload.token, purpose="email_verification")
    except AccountTokenError as error:
        raise HTTPException(400, str(error)) from error
    user.email_verified_at = datetime.now(UTC)
    workspace_id = user.memberships[0].workspace_id if user.memberships else None
    audit(
        session,
        event_type="account.email_verified",
        workspace_id=workspace_id,
        actor_user_id=user.id,
    )
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(409, "An account already uses this email address") from error


@router.post("/verification/resend", status_code=202)
async def resend_verification(
    auth: CsrfProtectedAuth, session: DatabaseSession
) -> dict[str, str | None]:
    development_token = None
    if auth.user.email_verified_at is None:
        raw = issue_token(session, user=auth.user, purpose="email_verification", minutes=60)
        if settings.app_env != "production":
            development_token = raw
        try:
            send_account_token(
                settings, email=auth.user.email, purpose="email_verification", token=raw
            )
        except Exception:
            logger.exception("Could not resend verification email")
    return {"status": "accepted", "development_token": development_token}


@router.post("/password-reset/request", status_code=202)
async def request_reset(payload: TokenRequest, session: DatabaseSession) -> dict[str, str]:
    user = session.scalar(select(User).where(User.email == payload.email.strip().casefold()))
    if user and user.is_active:
        raw = issue_token(session, user=user, purpose="password_reset", minutes=60)
        try:
            send_account_token(settings, email=user.email, purpose="password_reset", token=raw)
        except Exception:
            logger.exception("Could not send password reset email")
    return {"status": "accepted"}


@router.post("/password-reset/confirm", status_code=204)
async def confirm_reset(payload: PasswordResetConfirmation, session: DatabaseSession) -> None:
    try:
        user = reset_password(session, token=payload.token, new=payload.new_password)
    except AccountTokenError as error:
        raise HTTPException(400, str(error)) from error
    workspace_id = user.memberships[0].workspace_id if user.memberships else None
    audit(
        session,
        event_type="account.password_reset",
        workspace_id=workspace_id,
        actor_user_id=user.id,
    )
    session.commit()


@router.post("/password/change", status_code=204)
async def password_change(
    payload: PasswordChangeRequest, auth: CsrfProtectedAuth, session: DatabaseSession
) -> None:
    try:
        change_password(
            session, user=auth.user, current=payload.current_password, new=payload.new_password
        )
        audit(
            session,
            event_type="account.password_changed",
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user.id,
        )
        session.commit()
    except PasswordError as error:
        raise HTTPException(400, str(error)) from error


@router.patch("/account/email", status_code=202)
async def change_email(
    payload: EmailChangeRequest,
    auth: CsrfProtectedAuth,
    session: DatabaseSession,
) -> dict[str, str | None]:
    if not verify_password(auth.user, payload.current_password):
        raise HTTPException(400, "Current password is incorrect")
    if payload.email == auth.user.email:
        raise HTTPException(409, "The new email address is unchanged")
    if (
        session.scalar(
            select(User.id).where(
                User.id != auth.user.id,
                or_(User.email == payload.email, User.pending_email == payload.email),
            )
        )
        is not None
    ):
        raise HTTPException(409, "An account already uses this email address")

    auth.user.pending_email = payload.email
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(409, "An account already uses this email address") from error

    raw = issue_token(session, user=auth.user, purpose="email_change", minutes=60)
    development_token = raw if settings.app_env != "production" else None
    try:
        send_account_token(settings, email=payload.email, purpose="email_change", token=raw)
    except Exception:
        logger.exception("Could not send verification email after an address change")
        if settings.app_env == "production":
            auth.user.pending_email = None
            session.commit()
            raise HTTPException(503, "Verification email could not be delivered")
    audit(
        session,
        event_type="account.email_change_requested",
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user.id,
    )
    session.commit()
    return {"status": "verification_required", "development_token": development_token}


@router.delete("/account", status_code=204)
async def delete_account(
    payload: AccountDeletionRequest,
    response: Response,
    auth: CsrfProtectedAuth,
    session: DatabaseSession,
) -> None:
    if not verify_password(auth.user, payload.current_password):
        raise HTTPException(400, "Current password is incorrect")
    if len(workspace_users(session, auth.workspace_id)) != 1:
        raise HTTPException(
            409,
            "This workspace has other users; transfer or remove their access before deleting it",
        )

    audit(
        session,
        event_type="account.deleted",
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user.id,
    )
    session.flush()
    session.execute(delete(Workspace).where(Workspace.id == auth.workspace_id))
    session.execute(delete(User).where(User.id == auth.user.id))
    session.commit()
    _clear_auth_cookies(response)


@router.get("/sessions", response_model=list[SessionItem])
async def sessions(auth: CurrentAuth, session: DatabaseSession) -> list[SessionItem]:
    rows = session.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == auth.user.id, AuthSession.revoked_at.is_(None))
        .order_by(AuthSession.id.desc())
    ).all()
    return [
        SessionItem(
            id=row.id,
            created_at=row.created_at,
            last_used_at=row.last_used_at,
            expires_at=row.expires_at,
            current=row.id == auth.session.id,
        )
        for row in rows
    ]


@router.delete("/sessions/id/{session_id}", status_code=204)
async def revoke_one_session(
    session_id: int, auth: CsrfProtectedAuth, session: DatabaseSession
) -> None:
    row = session.scalar(
        select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == auth.user.id)
    )
    if row is None:
        raise HTTPException(404, "Session not found")
    row.revoked_at = datetime.now(UTC)
    session.commit()


@router.post("/sessions/revoke-others", status_code=204)
async def revoke_others(auth: CsrfProtectedAuth, session: DatabaseSession) -> None:
    revoke_user_sessions(session, auth.user.id, except_id=auth.session.id)
    session.commit()


def _admin(auth: CurrentAuth) -> None:
    if not auth.user.is_admin:
        raise HTTPException(403, "Administrator access required")


@router.get("/admin/users", response_model=list[UserAdminItem])
async def admin_users(auth: CurrentAuth, session: DatabaseSession) -> list[UserAdminItem]:
    _admin(auth)
    return [
        UserAdminItem.model_validate(user, from_attributes=True)
        for user in workspace_users(session, auth.workspace_id)
    ]


@router.patch("/admin/users/{user_id}", response_model=UserAdminItem)
async def admin_update_user(
    user_id: int, payload: UserAdminUpdate, auth: CsrfProtectedAuth, session: DatabaseSession
) -> UserAdminItem:
    _admin(auth)
    allowed = {user.id: user for user in workspace_users(session, auth.workspace_id)}
    target = allowed.get(user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    if target.id == auth.user.id and payload.is_active is False:
        raise HTTPException(409, "Cannot deactivate your own account")
    if target.id == auth.user.id and payload.is_admin is False:
        raise HTTPException(409, "Cannot remove your own administrator access")
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.is_admin is not None:
        target.is_admin = payload.is_admin
    if not target.is_active:
        revoke_user_sessions(session, target.id)
    audit(
        session,
        event_type="admin.user_updated",
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user.id,
        target_user_id=target.id,
        details=payload.model_dump(exclude_none=True),
    )
    session.commit()
    return UserAdminItem.model_validate(target, from_attributes=True)


@router.get("/admin/audit", response_model=list[dict])
async def admin_audit(auth: CurrentAuth, session: DatabaseSession) -> list[dict]:
    _admin(auth)
    rows = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == auth.workspace_id)
        .order_by(AuditEvent.id.desc())
        .limit(200)
    ).all()
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "actor_user_id": row.actor_user_id,
            "target_user_id": row.target_user_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]
