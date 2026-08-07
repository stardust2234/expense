from datetime import datetime

from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    id: int
    email: str
    display_name: str
    workspace_id: int
    trial_ends_at: datetime
    access_expires_at: datetime | None
    access_active: bool
