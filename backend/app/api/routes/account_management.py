import logging

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.auth_dependencies import AppSettings, CsrfProtectedAuth, DatabaseSession
from app.api.routes.auth_shared import clear_auth_cookies
from app.models import User, Workspace
from app.schemas.auth import AccountDeletionRequest, EmailChangeRequest, PasswordChangeRequest
from app.services.account_security_service import (
    PasswordError,
    audit,
    change_password,
    verify_password,
)
from app.services.email_token_workflow import deliver_email_token, prepare_email_token

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/password/change", status_code=204)
async def password_change(
    payload: PasswordChangeRequest, auth: CsrfProtectedAuth, session: DatabaseSession
) -> None:
    try:
        change_password(
            session,
            user=auth.user,
            current=payload.current_password,
            new=payload.new_password,
            current_session_id=auth.session.id,
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
    settings: AppSettings,
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

    delivery = prepare_email_token(
        session,
        user=auth.user,
        purpose="email_change",
        recipient=payload.email,
        minutes=60,
    )
    session.commit()
    development_token = delivery.raw_token if settings.app_env != "production" else None
    try:
        await deliver_email_token(settings, delivery)
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
    settings: AppSettings,
) -> None:
    if not verify_password(auth.user, payload.current_password):
        raise HTTPException(400, "Current password is incorrect")
    audit(
        session,
        event_type="account.deleted",
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user.id,
    )
    session.flush()
    workspace_delete = session.execute(
        delete(Workspace).where(
            Workspace.id == auth.workspace_id,
            Workspace.owner_user_id == auth.user.id,
        )
    )
    if workspace_delete.rowcount != 1:
        session.rollback()
        raise HTTPException(409, "Owned workspace could not be deleted")
    session.execute(delete(User).where(User.id == auth.user.id))
    session.commit()
    clear_auth_cookies(response, settings)
