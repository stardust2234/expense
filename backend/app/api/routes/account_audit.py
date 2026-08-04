from fastapi import APIRouter
from sqlalchemy import select

from app.api.auth_dependencies import CurrentAuth, DatabaseSession
from app.models import AuditEvent

router = APIRouter()


@router.get("/account/audit", response_model=list[dict])
async def account_audit(auth: CurrentAuth, session: DatabaseSession) -> list[dict]:
    rows = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.workspace_id == auth.workspace_id)
        .order_by(AuditEvent.id.desc())
        .limit(200)
    ).all()
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "actor_user_id": row.actor_user_id,
            "target_user_id": row.target_user_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]
