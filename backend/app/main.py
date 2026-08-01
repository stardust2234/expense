from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import select

from app.api.auth_dependencies import require_workspace_request
from app.api.routes.auth import router as auth_router
from app.api.routes.categories import router as categories_router
from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router
from app.api.routes.merchants import router as merchants_router
from app.api.routes.payment_cycles import router as payment_cycles_router
from app.api.routes.reports import router as reports_router
from app.api.routes.review_queue import router as review_queue_router
from app.api.routes.rules import router as rules_router
from app.api.routes.transactions import router as transactions_router
from app.config import get_settings
from app.database.session import SessionLocal
from app.models import Workspace
from app.services.commitment_reconciliation import reconcile_pending_commitments
from app.services.import_job_service import resume_incomplete_import_jobs

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    with SessionLocal() as session:
        workspace_ids = session.scalars(select(Workspace.id)).all()
    for workspace_id in workspace_ids:
        with SessionLocal() as session:
            session.info["workspace_id"] = workspace_id
            reconcile_pending_commitments(session)
            session.commit()
    resume_incomplete_import_jobs()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.include_router(auth_router, prefix="/api")
protected = [Depends(require_workspace_request)]
app.include_router(categories_router, prefix="/api", dependencies=protected)
app.include_router(health_router, prefix="/api")
app.include_router(imports_router, prefix="/api", dependencies=protected)
app.include_router(merchants_router, prefix="/api", dependencies=protected)
app.include_router(payment_cycles_router, prefix="/api", dependencies=protected)
app.include_router(review_queue_router, prefix="/api", dependencies=protected)
app.include_router(rules_router, prefix="/api", dependencies=protected)
app.include_router(transactions_router, prefix="/api", dependencies=protected)
app.include_router(reports_router, prefix="/api", dependencies=protected)
