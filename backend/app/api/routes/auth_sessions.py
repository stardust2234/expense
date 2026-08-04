import logging
from datetime import UTC, datetime
from secrets import token_urlsafe

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.auth_dependencies import AppSettings, CsrfProtectedAuth, CurrentAuth, DatabaseSession
from app.api.routes.auth_shared import (
    authenticated_user,
    clear_auth_cookies,
    issued_session_response,
    require_public_csrf,
    set_csrf_cookie,
    set_session_cookies,
)
from app.models import AuthSession
from app.schemas.auth import (
    AuthSessionResponse,
    BootstrapStatusResponse,
    CsrfResponse,
    LoginRequest,
    RegistrationRequest,
    SessionItem,
)
from app.services.account_security_service import audit, revoke_user_sessions
from app.services.auth_service import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AuthenticationError,
    BootstrapProtectionError,
    LoginThrottledError,
    RegistrationConflictError,
    administrator_bootstrap_required,
    enforce_registration_throttle,
    get_auth_session,
    login_throttle_keys,
    login_user,
    register_user,
    revoke_session,
    rotate_csrf,
    verify_csrf,
)
from app.services.client_ip import resolve_client_ip
from app.services.email_token_workflow import deliver_email_token, prepare_email_token

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/csrf", response_model=CsrfResponse)
async def get_csrf(
    response: Response,
    session: DatabaseSession,
    request: Request,
    settings: AppSettings,
) -> CsrfResponse:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    existing = get_auth_session(session, request.cookies.get(SESSION_COOKIE))
    if existing is not None:
        token = (
            cookie_token
            if cookie_token and verify_csrf(existing[0], cookie_token)
            else rotate_csrf(existing[0])
        )
    else:
        token = cookie_token or token_urlsafe(32)
    session.commit()
    set_csrf_cookie(response, token, settings)
    return CsrfResponse(csrf_token=token)


@router.post("/register", response_model=AuthSessionResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    response: Response,
    request: Request,
    session: DatabaseSession,
    settings: AppSettings,
    x_csrf_token: str | None = Header(default=None),
    x_admin_bootstrap_token: str | None = Header(default=None),
) -> AuthSessionResponse:
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    require_public_csrf(request, x_csrf_token)
    try:
        enforce_registration_throttle(
            session,
            client_ip=resolve_client_ip(request, trusted_proxy_cidrs=settings.trusted_proxy_cidrs),
            secret=settings.auth_throttle_secret,
        )
        session.commit()
        issued = register_user(
            session,
            email=payload.email,
            display_name=payload.display_name,
            password=payload.password,
            session_days=settings.session_days,
            bootstrap_secret=settings.admin_bootstrap_secret,
            supplied_bootstrap_token=x_admin_bootstrap_token,
        )
        delivery = prepare_email_token(
            session, user=issued.user, purpose="email_verification", minutes=60
        )
        session.commit()
    except LoginThrottledError as error:
        session.commit()
        raise HTTPException(status_code=429, detail=str(error)) from error
    except BootstrapProtectionError as error:
        session.rollback()
        raise HTTPException(status_code=403, detail=str(error)) from error
    except RegistrationConflictError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(error)) from error
    set_session_cookies(response, issued, settings)
    try:
        await deliver_email_token(settings, delivery)
    except Exception:
        logger.exception("Could not send verification email")
    return issued_session_response(issued)


@router.get("/bootstrap-status", response_model=BootstrapStatusResponse)
async def bootstrap_status(session: DatabaseSession) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(required=administrator_bootstrap_required(session))


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    session: DatabaseSession,
    settings: AppSettings,
    x_csrf_token: str | None = Header(default=None),
) -> AuthSessionResponse:
    require_public_csrf(request, x_csrf_token)
    try:
        identity_throttle_key, ip_throttle_key = login_throttle_keys(
            email=payload.email,
            client_ip=resolve_client_ip(request, trusted_proxy_cidrs=settings.trusted_proxy_cidrs),
            secret=settings.auth_throttle_secret,
        )
        issued = login_user(
            session,
            email=payload.email,
            password=payload.password,
            session_days=settings.session_days,
            identity_throttle_key=identity_throttle_key,
            ip_throttle_key=ip_throttle_key,
            existing_token=request.cookies.get(SESSION_COOKIE),
        )
    except LoginThrottledError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except AuthenticationError as error:
        session.commit()
        raise HTTPException(status_code=401, detail=str(error)) from error
    set_session_cookies(response, issued, settings)
    audit(
        session,
        event_type="account.login",
        workspace_id=issued.workspace_id,
        actor_user_id=issued.user.id,
    )
    session.commit()
    return issued_session_response(issued)


@router.get("/session", response_model=AuthSessionResponse)
async def current_session(auth: CurrentAuth) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=authenticated_user(auth.user, auth.workspace_id),
        expires_at=auth.session.expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    auth: CsrfProtectedAuth,
    session: DatabaseSession,
    settings: AppSettings,
) -> None:
    audit(
        session,
        event_type="account.logout",
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user.id,
    )
    revoke_session(session, auth.session)
    session.commit()
    clear_auth_cookies(response, settings)


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
