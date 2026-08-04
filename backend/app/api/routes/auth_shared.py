from hmac import compare_digest

from fastapi import HTTPException, Request, Response, status

from app.config import Settings
from app.models import User
from app.schemas.auth import AuthenticatedUser, AuthSessionResponse
from app.services.auth_service import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    IssuedSession,
    workspace_access_active,
)


def set_csrf_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_days * 24 * 60 * 60,
    )


def set_session_cookies(response: Response, issued: IssuedSession, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        issued.raw_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_days * 24 * 60 * 60,
    )
    set_csrf_cookie(response, issued.csrf_token, settings)


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=settings.auth_cookie_secure, samesite="lax"
    )
    response.delete_cookie(
        CSRF_COOKIE, path="/", secure=settings.auth_cookie_secure, samesite="lax"
    )


def authenticated_user(user: User, workspace_id: int) -> AuthenticatedUser:
    workspace = user.workspace
    if workspace is None or workspace.id != workspace_id:
        raise RuntimeError("Authenticated user does not own the requested workspace")
    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        workspace_id=workspace_id,
        email_verified=user.email_verified_at is not None,
        trial_ends_at=workspace.trial_ends_at,
        access_expires_at=workspace.access_expires_at,
        access_active=workspace_access_active(workspace),
    )


def issued_session_response(issued: IssuedSession) -> AuthSessionResponse:
    return AuthSessionResponse(
        user=authenticated_user(issued.user, issued.workspace_id),
        expires_at=issued.expires_at,
        csrf_token=issued.csrf_token,
    )


def require_public_csrf(request: Request, csrf_token: str | None) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    if not csrf_token or not cookie_token or not compare_digest(csrf_token, cookie_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
