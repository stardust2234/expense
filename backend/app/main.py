import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

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
from app.config import Settings, get_settings
from app.services.import_job_service import shutdown_import_jobs
from app.services.startup_maintenance import run_startup_maintenance

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_lifespan(
    *,
    startup: Callable[[], object] = run_startup_maintenance,
    shutdown: Callable[[], None] = shutdown_import_jobs,
) -> Lifespan:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.startup_maintenance = await asyncio.to_thread(startup)
        try:
            yield
        finally:
            await asyncio.to_thread(shutdown)

    return lifespan


def create_app(
    app_settings: Settings | None = None,
    *,
    lifespan: Lifespan | None = None,
) -> FastAPI:
    settings = app_settings or get_settings()
    application = FastAPI(
        title=settings.app_name,
        lifespan=lifespan or create_lifespan(),
    )
    application.state.settings = settings
    application.include_router(auth_router, prefix="/api")
    application.include_router(health_router, prefix="/api")

    protected = APIRouter(dependencies=[Depends(require_workspace_request)])
    for router in (
        categories_router,
        imports_router,
        merchants_router,
        payment_cycles_router,
        review_queue_router,
        rules_router,
        transactions_router,
        reports_router,
    ):
        protected.include_router(router)
    application.include_router(protected, prefix="/api")
    return application


app = create_app()
