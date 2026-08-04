import logging

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from app.api.auth_dependencies import AppSettings, CsrfProtectedAuth, CurrentAuth, DatabaseSession
from app.services.account_security_service import audit
from app.services.mail_service import check_smtp_readiness, send_delivery_test

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/account/email-delivery/readiness")
async def account_email_readiness(auth: CurrentAuth, settings: AppSettings) -> dict[str, str]:
    try:
        if settings.smtp_host:
            await run_in_threadpool(check_smtp_readiness, settings)
        else:
            check_smtp_readiness(settings)
    except Exception as error:
        logger.exception("Owner SMTP readiness check failed")
        raise HTTPException(503, "Email delivery is unavailable") from error
    return {"status": "ready"}


@router.post("/account/email-delivery/test", status_code=202)
async def account_email_delivery_test(
    auth: CsrfProtectedAuth,
    session: DatabaseSession,
    settings: AppSettings,
) -> dict[str, str]:
    try:
        if settings.smtp_host:
            await run_in_threadpool(send_delivery_test, settings, email=auth.user.email)
        else:
            send_delivery_test(settings, email=auth.user.email)
    except Exception as error:
        logger.exception("Owner email delivery test failed")
        raise HTTPException(503, "Test email could not be delivered") from error
    audit(
        session,
        event_type="account.email_delivery_tested",
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user.id,
    )
    session.commit()
    return {"status": "accepted"}
