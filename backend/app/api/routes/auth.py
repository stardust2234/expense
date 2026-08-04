from fastapi import APIRouter

from app.api.routes.account_audit import router as account_audit_router
from app.api.routes.account_management import router as account_management_router
from app.api.routes.account_recovery import router as account_recovery_router
from app.api.routes.auth_sessions import router as auth_sessions_router
from app.api.routes.email_diagnostics import router as email_diagnostics_router

router = APIRouter(prefix="/auth", tags=["authentication"])
router.include_router(auth_sessions_router)
router.include_router(account_recovery_router)
router.include_router(account_management_router)
router.include_router(account_audit_router)
router.include_router(email_diagnostics_router)
