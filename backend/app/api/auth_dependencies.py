from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.session import get_database_session
from app.models import AuthSession, User
from app.services.auth_service import (
    CSRF_COOKIE,
    CSRF_HEADER,
    SESSION_COOKIE,
    get_auth_session,
    verify_csrf,
    workspace_access_active,
)

DatabaseSession = Annotated[Session, Depends(get_database_session)]


async def get_application_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_application_settings)]


@dataclass(frozen=True)
class AuthContext:
    user: User
    workspace_id: int
    session: AuthSession


async def get_current_auth_context(request: Request, database: DatabaseSession) -> AuthContext:
    result = get_auth_session(database, request.cookies.get(SESSION_COOKIE))
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    auth_session, workspace_id = result
    return AuthContext(
        user=auth_session.user,
        workspace_id=workspace_id,
        session=auth_session,
    )


CurrentAuth = Annotated[AuthContext, Depends(get_current_auth_context)]


async def require_authenticated_csrf(request: Request, auth: CurrentAuth) -> AuthContext:
    validate_csrf(request, auth)
    return auth


CsrfProtectedAuth = Annotated[AuthContext, Depends(require_authenticated_csrf)]


def validate_csrf(request: Request, auth: AuthContext) -> None:
    header_token = request.headers.get(CSRF_HEADER)
    cookie_token = request.cookies.get(CSRF_COOKIE)
    if header_token != cookie_token or not verify_csrf(auth.session, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


async def require_workspace_request(
    request: Request,
    database: DatabaseSession,
    auth: CurrentAuth,
) -> AuthContext:
    if auth.user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Email verification required")
    workspace = auth.user.workspace
    if workspace is None:
        raise HTTPException(status_code=403, detail="Workspace access is unavailable")
    if not workspace_access_active(workspace):
        raise HTTPException(status_code=402, detail="Your free trial has expired")
    database.info["workspace_id"] = auth.workspace_id
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        validate_csrf(request, auth)
    return auth
