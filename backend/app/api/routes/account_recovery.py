import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.auth_dependencies import AppSettings, CsrfProtectedAuth, DatabaseSession
from app.models import User
from app.schemas.auth import PasswordResetConfirmation, TokenConfirmation, TokenRequest
from app.services.account_security_service import (
    AccountTokenError,
    audit,
    consume_token,
    reset_password,
)
from app.services.auth_service import LoginThrottledError, enforce_email_throttle
from app.services.client_ip import resolve_client_ip
from app.services.email_token_workflow import deliver_email_token, prepare_email_token

router = APIRouter()
logger = logging.getLogger(__name__)


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
    workspace_id = user.workspace.id if user.workspace else None
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
    request: Request,
    auth: CsrfProtectedAuth,
    session: DatabaseSession,
    settings: AppSettings,
) -> dict[str, str | None]:
    try:
        enforce_email_throttle(
            session,
            action="verification_resend",
            identity=str(auth.user.id),
            client_ip=resolve_client_ip(request, trusted_proxy_cidrs=settings.trusted_proxy_cidrs),
            secret=settings.auth_throttle_secret,
        )
        session.commit()
    except LoginThrottledError as error:
        session.commit()
        raise HTTPException(429, str(error)) from error
    development_token = None
    if auth.user.email_verified_at is None:
        delivery = prepare_email_token(
            session, user=auth.user, purpose="email_verification", minutes=60
        )
        session.commit()
        if settings.app_env != "production":
            development_token = delivery.raw_token
        try:
            await deliver_email_token(settings, delivery)
        except Exception:
            logger.exception("Could not resend verification email")
    return {"status": "accepted", "development_token": development_token}


@router.post("/password-reset/request", status_code=202)
async def request_reset(
    payload: TokenRequest,
    request: Request,
    session: DatabaseSession,
    settings: AppSettings,
) -> dict[str, str]:
    try:
        enforce_email_throttle(
            session,
            action="password_reset",
            identity=payload.email,
            client_ip=resolve_client_ip(request, trusted_proxy_cidrs=settings.trusted_proxy_cidrs),
            secret=settings.auth_throttle_secret,
        )
        session.commit()
    except LoginThrottledError as error:
        session.commit()
        raise HTTPException(429, str(error)) from error
    user = session.scalar(select(User).where(User.email == payload.email.strip().casefold()))
    if user:
        delivery = prepare_email_token(session, user=user, purpose="password_reset", minutes=60)
        session.commit()
        try:
            await deliver_email_token(settings, delivery)
        except Exception:
            logger.exception("Could not send password reset email")
    return {"status": "accepted"}


@router.post("/password-reset/confirm", status_code=204)
async def confirm_reset(payload: PasswordResetConfirmation, session: DatabaseSession) -> None:
    try:
        user = reset_password(session, token=payload.token, new=payload.new_password)
    except AccountTokenError as error:
        raise HTTPException(400, str(error)) from error
    workspace_id = user.workspace.id if user.workspace else None
    audit(
        session,
        event_type="account.password_reset",
        workspace_id=workspace_id,
        actor_user_id=user.id,
    )
    session.commit()
