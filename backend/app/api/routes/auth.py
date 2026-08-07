from fastapi import APIRouter, Request

from app.api.auth_dependencies import CurrentAuth
from app.schemas.auth import AuthenticatedUser
from app.services.workspace_access_service import workspace_access_active

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/config")
async def auth0_config(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "domain": settings.auth0_domain,
        "client_id": settings.auth0_client_id,
        "audience": settings.auth0_audience,
    }


@router.get("/me", response_model=AuthenticatedUser)
async def authenticated_user(auth: CurrentAuth) -> AuthenticatedUser:
    workspace = auth.user.workspace
    if workspace is None:
        raise RuntimeError("Authenticated Auth0 user has no workspace")
    return AuthenticatedUser(
        id=auth.user.id,
        email=auth.user.email,
        display_name=auth.user.display_name,
        workspace_id=workspace.id,
        trial_ends_at=workspace.trial_ends_at,
        access_expires_at=workspace.access_expires_at,
        access_active=workspace_access_active(workspace),
    )
