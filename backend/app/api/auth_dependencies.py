import asyncio
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.database.session import get_database_session
from app.models import User
from app.services.auth0_service import Auth0Identity, Auth0TokenError
from app.services.workspace_access_service import workspace_access_active
from app.services.workspace_identity_service import (
    WorkspaceIdentityConflict,
    resolve_workspace_owner,
)

DatabaseSession = Annotated[Session, Depends(get_database_session)]
bearer = HTTPBearer(auto_error=False)


async def get_application_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_application_settings)]


async def get_auth0_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Auth0Identity:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(401, "Bearer authentication required")
    try:
        return await asyncio.to_thread(
            request.app.state.auth0_verifier.verify, credentials.credentials
        )
    except Auth0TokenError as error:
        raise HTTPException(401, str(error)) from error


@dataclass(frozen=True)
class AuthContext:
    user: User
    workspace_id: int
    identity: Auth0Identity


async def get_current_auth_context(
    identity: Annotated[Auth0Identity, Depends(get_auth0_identity)],
    database: DatabaseSession,
) -> AuthContext:
    try:
        user = resolve_workspace_owner(database, identity)
    except WorkspaceIdentityConflict as error:
        raise HTTPException(409, str(error)) from error
    if user.workspace is None:
        raise HTTPException(403, "Workspace access is unavailable")
    database.info["workspace_id"] = user.workspace.id
    return AuthContext(user=user, workspace_id=user.workspace.id, identity=identity)


CurrentAuth = Annotated[AuthContext, Depends(get_current_auth_context)]


async def require_workspace_request(auth: CurrentAuth, database: DatabaseSession) -> AuthContext:
    workspace = auth.user.workspace
    if workspace is None:
        raise HTTPException(403, "Workspace access is unavailable")
    if not workspace_access_active(workspace):
        raise HTTPException(402, "Your free trial has expired")
    database.info["workspace_id"] = auth.workspace_id
    return auth
