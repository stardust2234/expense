from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from app.database.engine import engine
from app.models.workspace_owned import WorkspaceOwned

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "do_orm_execute")
def enforce_workspace_queries(orm_execute_state) -> None:
    """Apply workspace ownership to every ORM select, update, and delete."""
    workspace_id = orm_execute_state.session.info.get("workspace_id")
    if workspace_id is None or orm_execute_state.execution_options.get("system_unscoped"):
        return
    if orm_execute_state.is_select:
        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                WorkspaceOwned,
                lambda entity: entity.workspace_id == workspace_id,
                include_aliases=True,
            )
        )
    elif orm_execute_state.is_update or orm_execute_state.is_delete:
        mapper = orm_execute_state.bind_arguments.get("mapper")
        if mapper is not None and issubclass(mapper.class_, WorkspaceOwned):
            orm_execute_state.statement = orm_execute_state.statement.where(
                mapper.class_.workspace_id == workspace_id
            )


@event.listens_for(Session, "before_flush")
def enforce_workspace_writes(session: Session, _flush_context, _instances) -> None:
    workspace_id = session.info.get("workspace_id")
    if workspace_id is None:
        return
    for record in session.new:
        if isinstance(record, WorkspaceOwned):
            if record.workspace_id is None:
                record.workspace_id = workspace_id
            elif record.workspace_id != workspace_id:
                raise PermissionError("Cannot create data in another workspace")
    for record in session.dirty | session.deleted:
        if isinstance(record, WorkspaceOwned) and record.workspace_id != workspace_id:
            raise PermissionError("Cannot change data in another workspace")


async def get_database_session() -> AsyncIterator[Session]:
    with SessionLocal() as session:
        yield session
