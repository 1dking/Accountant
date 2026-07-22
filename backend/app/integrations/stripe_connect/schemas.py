
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StripeConnectStartResponse(BaseModel):
    url: str


class StripeConnectStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stripe_account_id: str
    charges_enabled: bool
    payouts_enabled: bool
    details_submitted: bool
    is_active: bool
    onboarding_completed_at: datetime | None = None
    created_at: datetime
