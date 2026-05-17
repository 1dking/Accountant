
import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    message: str
    resource_type: str | None = None
    resource_id: str | None = None
    is_read: bool
    link_path: str | None = None
    contact_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
