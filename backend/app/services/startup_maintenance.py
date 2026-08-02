import logging
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models import Workspace
from app.services.commitment_reconciliation import reconcile_pending_commitments
from app.services.import_job_service import resume_incomplete_import_jobs

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]


@dataclass(frozen=True)
class StartupMaintenanceResult:
    reconciled_workspaces: int
    failed_workspace_ids: tuple[int, ...]
    resumed_import_jobs: int


def run_startup_maintenance(
    *,
    session_factory: SessionFactory = SessionLocal,
    reconcile: Callable[[Session], object] = reconcile_pending_commitments,
    resume_jobs: Callable[[], int] = resume_incomplete_import_jobs,
) -> StartupMaintenanceResult:
    """Repair persisted state before serving, isolating workspace-local failures."""
    with session_factory() as session:
        workspace_ids = tuple(session.scalars(select(Workspace.id)).all())

    reconciled = 0
    failed: list[int] = []
    for workspace_id in workspace_ids:
        try:
            with session_factory() as session:
                session.info["workspace_id"] = workspace_id
                reconcile(session)
                session.commit()
            reconciled += 1
        except Exception:
            failed.append(workspace_id)
            logger.exception(
                "Startup commitment reconciliation failed for workspace %s",
                workspace_id,
            )

    resumed = resume_jobs()
    return StartupMaintenanceResult(
        reconciled_workspaces=reconciled,
        failed_workspace_ids=tuple(failed),
        resumed_import_jobs=resumed,
    )
