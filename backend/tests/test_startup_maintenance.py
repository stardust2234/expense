import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.main import create_app, create_lifespan
from app.models import Workspace
from app.services.startup_maintenance import run_startup_maintenance


def workspace_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                Workspace(name="First", is_claimed=True),
                Workspace(name="Second", is_claimed=True),
                Workspace(name="Third", is_claimed=True),
            ]
        )
        session.commit()
    return factory


def test_startup_maintenance_isolates_workspace_failures() -> None:
    factory = workspace_session_factory()
    visited: list[int] = []

    def reconcile(session: Session) -> None:
        workspace_id = session.info["workspace_id"]
        visited.append(workspace_id)
        if workspace_id == 2:
            raise RuntimeError("broken workspace")

    result = run_startup_maintenance(
        session_factory=factory,
        reconcile=reconcile,
        resume_jobs=lambda: 4,
    )

    assert visited == [1, 2, 3]
    assert result.reconciled_workspaces == 2
    assert result.failed_workspace_ids == (2,)
    assert result.resumed_import_jobs == 4


def test_startup_maintenance_keeps_workspace_discovery_failures_fatal() -> None:
    def unavailable_database():
        raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        run_startup_maintenance(session_factory=unavailable_database)


@pytest.mark.anyio
async def test_application_lifespan_runs_startup_and_shutdown_off_app_boundary(
    monkeypatch,
) -> None:
    calls: list[str] = []

    async def immediately(function):
        return function()

    monkeypatch.setattr("app.main.asyncio.to_thread", immediately)
    lifespan = create_lifespan(
        startup=lambda: calls.append("startup") or {"resumed": 0},
        shutdown=lambda: calls.append("shutdown"),
    )
    application = create_app(lifespan=lifespan)

    async with application.router.lifespan_context(application):
        assert calls == ["startup"]
        assert application.state.startup_maintenance == {"resumed": 0}

    assert calls == ["startup", "shutdown"]
