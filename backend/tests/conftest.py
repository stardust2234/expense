import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.api.auth_dependencies import require_workspace_request
from app.main import app
from app.models.workspace_owned import WorkspaceOwned


@event.listens_for(Session, "before_flush")
def assign_test_workspace(session: Session, _flush_context, _instances) -> None:
    missing = [
        record
        for record in session.new
        if isinstance(record, WorkspaceOwned) and record.workspace_id is None
    ]
    if not missing:
        return
    connection = session.connection()
    connection.exec_driver_sql(
        "INSERT OR IGNORE INTO users "
        "(id, email, display_name, password_hash) VALUES "
        "(1, 'test-owner@example.com', 'Test Owner', 'test-placeholder')"
    )
    connection.exec_driver_sql(
        "INSERT OR IGNORE INTO workspaces "
        "(id, owner_user_id, name, is_claimed) VALUES "
        "(1, 1, 'Test workspace', 1)"
    )
    for record in missing:
        record.workspace_id = 1


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "auth_boundary: exercise the real authentication and workspace boundary",
    )


@pytest.fixture(autouse=True)
def bypass_auth_for_service_contract_tests(request):
    if request.node.get_closest_marker("auth_boundary") is not None:
        yield
        return

    async def allow_existing_contracts() -> None:
        return None

    app.dependency_overrides[require_workspace_request] = allow_existing_contracts
    try:
        yield
    finally:
        app.dependency_overrides.pop(require_workspace_request, None)
