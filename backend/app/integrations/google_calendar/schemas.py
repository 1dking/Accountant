
import uuid
from datetime import datetime

from pydantic import BaseModel


class GoogleCalendarAccountResponse(BaseModel):
    id: uuid.UUID
    email: str
    is_active: bool
    last_sync_at: datetime | None = None
    selected_calendar_id: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class GoogleCalendarConnectResponse(BaseModel):
    auth_url: str


class GoogleCalendarInfo(BaseModel):
    id: str
    summary: str
    description: str | None = None
    primary: bool = False
    background_color: str | None = None


class SyncResult(BaseModel):
    events_pushed: int = 0
    events_pulled: int = 0
    errors: list[str] = []
