from datetime import UTC, datetime

from app.models import Workspace


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def workspace_access_ends_at(workspace: Workspace) -> datetime:
    trial_end = _aware(workspace.trial_ends_at)
    if workspace.access_expires_at is None:
        return trial_end
    return max(trial_end, _aware(workspace.access_expires_at))


def workspace_access_active(workspace: Workspace, *, now: datetime | None = None) -> bool:
    return workspace_access_ends_at(workspace) > (now or datetime.now(UTC))
